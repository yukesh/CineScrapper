
#!/usr/bin/env python3
"""
Reconcile a local soundtrack manifest with MongoDB.

Features:
- Matches cinema titles using exact and normalized comparisons.
- Detects likely title mismatches and year-folder mismatches.
- Generates fuzzy-match suggestions with confidence scores.
- Produces CSV reports for new tracks, unmatched cinemas,
  candidate matches, and reconciliation summary.
- Preserves existing track metadata and add_collection values.
- Sets add_collection=False for new tracks.
- Sets downloaded=True when supported local audio tracks are found.
- Ignores Background Score; processes manifest OST tracks only.
- Uses certifi for TLS-enabled MongoDB connections.
- Defaults to dry-run; use --apply to write changes.

Fuzzy suggestions are never automatically used to update MongoDB.
"""

import argparse
import csv
import difflib
import json
import logging
import os
import re
import sys

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger("reconcile_soundtracks")

AUDIO_EXTENSIONS = {
    ".m4a",
    ".flac",
    ".alac",
    ".mp3",
    ".aac",
    ".wav",
    ".aiff",
    ".ogg",
    ".opus",
}

DEFAULT_COLLECTION = "cinemas"
DEFAULT_SOUNDTRACK_NAME = "Original Soundtrack"
MAX_REVIEW_CANDIDATES = 3


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def configure_logging(level):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


# ---------------------------------------------------------------------------
# MongoDB connection
# ---------------------------------------------------------------------------

def create_mongo_client(connection_string):
    """Create a MongoDB client using the same TLS approach as MongoCinemaWriter."""
    try:
        from pymongo import MongoClient
    except ImportError as exception:
        raise RuntimeError(
            "MongoDB support requires pymongo. "
            "Install it with: python -m pip install pymongo"
        ) from exception

    parsed = urlparse(connection_string)
    options = parse_qs(parsed.query)

    tls_enabled = parsed.scheme == "mongodb+srv" or any(
        value.lower() in {"true", "1", "yes"}
        for key in ("tls", "ssl")
        for value in options.get(key, [])
    )

    client_options = {
        "serverSelectionTimeoutMS": 10000,
    }

    if tls_enabled:
        try:
            import certifi
        except ImportError as exception:
            raise RuntimeError(
                "TLS MongoDB connections require certifi. "
                "Install it with: python -m pip install certifi"
            ) from exception

        client_options["tlsCAFile"] = certifi.where()

    return MongoClient(connection_string, **client_options)


# ---------------------------------------------------------------------------
# Title normalization and similarity
# ---------------------------------------------------------------------------

def normalize_text(value):
    """
    Normalize title text for comparisons.

    Examples:
        "Film: The Beginning" -> "film the beginning"
        "Film & Friends"      -> "film and friends"
        "FILM-FRIENDS"        -> "film friends"
    """
    if value is None:
        return ""

    value = str(value).casefold().strip()

    # Treat ampersand and the word "and" consistently.
    value = value.replace("&", " and ")

    # Remove common punctuation and separators.
    value = re.sub(r"[\[\](){}]", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)

    return " ".join(value.split())


def title_similarity(first_title, second_title):
    """
    Return a title similarity score from 0 to 100.

    Uses:
    - Character-sequence similarity.
    - Word-set similarity.

    This function is used for suggestions, not automatic fuzzy matching.
    """
    first = normalize_text(first_title)
    second = normalize_text(second_title)

    if not first or not second:
        return 0

    if first == second:
        return 100

    character_score = difflib.SequenceMatcher(
        None,
        first,
        second,
    ).ratio()

    first_words = set(first.split())
    second_words = set(second.split())

    union = first_words | second_words
    intersection = first_words & second_words

    word_score = len(intersection) / len(union) if union else 0

    # Character spelling similarity gets slightly more weight.
    combined_score = (
            0.65 * character_score
            + 0.35 * word_score
    )

    return round(combined_score * 100)


def safe_year(value):
    """Convert a year to an integer when possible."""
    if value is None:
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def document_year(document):
    return safe_year(document.get("year"))


# ---------------------------------------------------------------------------
# MongoDB cinema catalogue
# ---------------------------------------------------------------------------

def load_cinema_catalogue(collection):
    """
    Load cinema titles and years for matching across all years.

    This allows the matcher to detect a title that exists in MongoDB
    under a different year from the local music folder.
    """
    documents = list(
        collection.find(
            {},
            {
                "title": 1,
                "year": 1,
            },
        )
    )

    logger.info(
        "Loaded %d cinema documents for title comparison.",
        len(documents),
    )

    return documents


def rank_candidates(film_title, year, catalogue):
    """
    Return the best candidate cinema documents across all years.

    Each result contains a document, score, and likely mismatch reason.
    """
    target_normalized = normalize_text(film_title)
    target_year = safe_year(year)

    candidates = []

    for document in catalogue:
        candidate_title = str(document.get("title") or "").strip()
        candidate_year = document_year(document)

        if not candidate_title:
            continue

        score = title_similarity(film_title, candidate_title)
        normalized_candidate = normalize_text(candidate_title)

        if normalized_candidate == target_normalized:
            score = 100

        # Rank by title similarity first. For equal scores, prefer
        # the same year, then a deterministic title ordering.
        same_year = (
                target_year is not None
                and candidate_year == target_year
        )

        candidates.append({
            "document": document,
            "score": score,
            "same_year": same_year,
            "reason": explain_candidate(
                film_title,
                target_year,
                candidate_title,
                candidate_year,
                score,
            ),
        })

    candidates.sort(
        key=lambda item: (
            item["score"],
            item["same_year"],
            str(item["document"].get("title") or "").casefold(),
        ),
        reverse=True,
    )

    return candidates[:MAX_REVIEW_CANDIDATES]


def explain_candidate(
        local_title,
        local_year,
        candidate_title,
        candidate_year,
        score,
):
    """Explain why a candidate might be relevant."""
    local_normalized = normalize_text(local_title)
    candidate_normalized = normalize_text(candidate_title)

    if local_normalized == candidate_normalized:
        if local_year == candidate_year:
            return "Normalized title and year match"

        return "Same normalized title, different year"

    if local_year != candidate_year:
        if score >= 85:
            return "Similar title and different year"
        if score >= 65:
            return "Possible title variation and different year"

    if score >= 95:
        return "Likely punctuation or formatting difference"

    if score >= 85:
        return "Very similar title or minor spelling difference"

    if score >= 70:
        return "Possible spelling or word-order difference"

    if score >= 50:
        return "Weak title similarity; manual review recommended"

    return "Low similarity; probably unrelated"


def find_cinema(film_title, year, catalogue):
    """
    Find a safe automatic match.

    Automatic matching:
    1. Exact title and year.
    2. One normalized-title match within the same year.

    Fuzzy matches and matches in a different year are review suggestions
    only; they are not selected automatically.
    """
    target_title = str(film_title or "").strip()
    target_year = safe_year(year)
    target_normalized = normalize_text(target_title)

    if not target_title or target_year is None:
        return None, "invalid_title_or_year", []

    # Exact title/year match.
    exact_matches = [
        document
        for document in catalogue
        if document.get("title") == target_title
           and document_year(document) == target_year
    ]

    if len(exact_matches) == 1:
        return exact_matches[0], None, []

    if len(exact_matches) > 1:
        return None, "ambiguous_match", rank_candidates(
            target_title,
            target_year,
            catalogue,
        )

    # Normalized title/year match.
    normalized_matches = [
        document
        for document in catalogue
        if normalize_text(document.get("title")) == target_normalized
           and document_year(document) == target_year
    ]

    if len(normalized_matches) == 1:
        matched_document = normalized_matches[0]

        logger.info(
            "Normalized match: %r (%s) -> %r (%s)",
            target_title,
            target_year,
            matched_document.get("title"),
            document_year(matched_document),
        )

        return matched_document, None, []

    if len(normalized_matches) > 1:
        return None, "ambiguous_match", rank_candidates(
            target_title,
            target_year,
            catalogue,
        )

    # Detect an identical normalized title under another year.
    other_year_matches = [
        document
        for document in catalogue
        if normalize_text(document.get("title")) == target_normalized
           and document_year(document) != target_year
    ]

    candidates = rank_candidates(
        target_title,
        target_year,
        catalogue,
    )

    if other_year_matches:
        return None, "year_mismatch", candidates

    # No exact or normalized match. Suggest fuzzy candidates for review.
    return None, "fuzzy_match_review", candidates


# ---------------------------------------------------------------------------
# Manifest loading
# ---------------------------------------------------------------------------

def load_manifest(manifest_path):
    path = Path(manifest_path).expanduser()

    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if isinstance(data, list):
        entries = data
    elif isinstance(data, dict):
        entries = None

        for key in ("films", "cinemas", "items", "entries"):
            if isinstance(data.get(key), list):
                entries = data[key]
                break

        if entries is None:
            raise ValueError(
                "Manifest must be a list or contain a list under "
                "'films', 'cinemas', 'items', or 'entries'."
            )
    else:
        raise ValueError("Unsupported manifest JSON structure.")

    if not all(isinstance(entry, dict) for entry in entries):
        raise ValueError("Every manifest entry must be a JSON object.")

    return entries


def get_manifest_tracks(entry):
    """Return valid audio tracks from one manifest entry."""
    tracks = entry.get("tracks", [])

    if not isinstance(tracks, list):
        logger.warning(
            "Invalid tracks list for %r (%s)",
            entry.get("film_title") or entry.get("title"),
            entry.get("year"),
            )
        return []

    valid_tracks = []

    for track in tracks:
        if not isinstance(track, dict):
            logger.warning("Ignoring invalid track entry: %r", track)
            continue

        filename = str(track.get("filename") or "").strip()
        relative_path = str(track.get("relative_path") or "").strip()

        if not filename or not relative_path:
            logger.warning(
                "Ignoring track missing filename or relative_path: %r",
                track,
            )
            continue

        if Path(filename).suffix.lower() not in AUDIO_EXTENSIONS:
            logger.warning("Ignoring unsupported audio file: %s", filename)
            continue

        valid_tracks.append({
            **track,
            "filename": filename,
            "relative_path": relative_path,
        })

    return valid_tracks


# ---------------------------------------------------------------------------
# Track reconciliation
# ---------------------------------------------------------------------------

def track_identity(track):
    """Use normalized filename as the primary track identity."""
    filename = str(track.get("filename") or "").strip()

    if filename:
        return normalize_text(filename)

    return normalize_text(track.get("relative_path") or "")


def merge_tracks(existing_tracks, local_tracks):
    """
    Merge local tracks into existing tracks.

    Existing metadata and add_collection values are preserved.

    Returns:
        merged_tracks, added_tracks, matched_count
    """
    merged = []
    existing_by_identity = {}

    for existing in existing_tracks:
        if not isinstance(existing, dict):
            logger.warning(
                "Ignoring unexpected existing track structure: %r",
                existing,
            )
            continue

        identity = track_identity(existing)

        if identity:
            existing_by_identity.setdefault(identity, []).append(existing)
        else:
            merged.append(dict(existing))

    added_tracks = []
    matched_count = 0
    seen_local = set()

    for local in local_tracks:
        identity = track_identity(local)

        if not identity:
            logger.warning("Cannot identify track: %r", local)
            continue

        if identity in seen_local:
            logger.warning(
                "Duplicate track in manifest ignored: %s",
                local.get("filename"),
            )
            continue

        seen_local.add(identity)
        matches = existing_by_identity.get(identity, [])

        if matches:
            existing = matches.pop(0)
            updated = dict(existing)

            # Refresh local file details while preserving other metadata.
            updated["filename"] = local["filename"]
            updated["relative_path"] = local["relative_path"]

            updated.setdefault("add_collection", False)

            for key, value in local.items():
                if key not in updated:
                    updated[key] = value

            merged.append(updated)
            matched_count += 1
        else:
            new_track = dict(local)
            new_track.setdefault("add_collection", False)

            merged.append(new_track)
            added_tracks.append(new_track)

    # Do not delete tracks absent from this particular scan.
    for remaining in existing_by_identity.values():
        merged.extend(remaining)

    return merged, added_tracks, matched_count


# ---------------------------------------------------------------------------
# CSV reports
# ---------------------------------------------------------------------------

ADDED_TRACK_FIELDS = [
    "film_title",
    "year",
    "language",
    "language_folder",
    "filename",
    "relative_path",
    "add_collection",
    "action",
]

NOT_FOUND_FIELDS = [
    "film_title",
    "year",
    "reason",
    "status",
    "best_candidate_title",
    "best_candidate_year",
    "best_candidate_score",
    "best_candidate_reason",
]

MATCH_REVIEW_FIELDS = [
    "local_title",
    "local_year",
    "match_status",
    "candidate_1_title",
    "candidate_1_year",
    "candidate_1_score",
    "candidate_1_reason",
    "candidate_2_title",
    "candidate_2_year",
    "candidate_2_score",
    "candidate_2_reason",
    "candidate_3_title",
    "candidate_3_year",
    "candidate_3_score",
    "candidate_3_reason",
]


def write_csv(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)

    logger.info("Report generated: %s (%d rows)", path, len(rows))


def build_added_track_rows(entry, added_tracks, action):
    film_title = entry.get("film_title") or entry.get("title") or ""

    return [
        {
            "film_title": film_title,
            "year": entry.get("year", ""),
            "language": entry.get("language", ""),
            "language_folder": entry.get("language_folder", ""),
            "filename": track.get("filename", ""),
            "relative_path": track.get("relative_path", ""),
            "add_collection": track.get("add_collection", False),
            "action": action,
        }
        for track in added_tracks
    ]


def build_match_review_row(entry, status, candidates):
    row = {
        "local_title": entry.get("film_title") or entry.get("title") or "",
        "local_year": entry.get("year", ""),
        "match_status": status,
    }

    for index in range(MAX_REVIEW_CANDIDATES):
        prefix = f"candidate_{index + 1}"

        if index >= len(candidates):
            row[f"{prefix}_title"] = ""
            row[f"{prefix}_year"] = ""
            row[f"{prefix}_score"] = ""
            row[f"{prefix}_reason"] = ""
            continue

        candidate = candidates[index]
        document = candidate["document"]

        row[f"{prefix}_title"] = document.get("title", "")
        row[f"{prefix}_year"] = document.get("year", "")
        row[f"{prefix}_score"] = candidate["score"]
        row[f"{prefix}_reason"] = candidate["reason"]

    return row


def build_not_found_row(entry, reason, candidates):
    best = candidates[0] if candidates else None
    best_document = best["document"] if best else {}

    return {
        "film_title": entry.get("film_title") or entry.get("title") or "",
        "year": entry.get("year", ""),
        "reason": reason,
        "status": "NEEDS_REVIEW",
        "best_candidate_title": best_document.get("title", ""),
        "best_candidate_year": best_document.get("year", ""),
        "best_candidate_score": best["score"] if best else "",
        "best_candidate_reason": best["reason"] if best else "",
    }


# ---------------------------------------------------------------------------
# Reconcile one cinema
# ---------------------------------------------------------------------------

def reconcile_cinema(collection, catalogue, entry, apply_changes):
    film_title = str(
        entry.get("film_title") or entry.get("title") or ""
    ).strip()

    year = entry.get("year")

    if not film_title or safe_year(year) is None:
        logger.error("Manifest entry missing a valid title or year: %r", entry)

        return {
            "status": "invalid",
            "added_tracks": [],
            "matched": 0,
            "not_found": None,
            "review": None,
        }

    local_tracks = get_manifest_tracks(entry)

    if not local_tracks:
        logger.warning(
            "No supported audio tracks for %r (%s); skipping",
            film_title,
            year,
        )

        return {
            "status": "no_audio",
            "added_tracks": [],
            "matched": 0,
            "not_found": None,
            "review": None,
        }

    document, match_error, candidates = find_cinema(
        film_title,
        year,
        catalogue,
    )

    if document is None:
        logger.warning(
            "No safe automatic match for %r (%s): %s",
            film_title,
            year,
            match_error,
        )

        review_row = build_match_review_row(
            entry,
            match_error,
            candidates,
        )

        not_found_row = build_not_found_row(
            entry,
            match_error,
            candidates,
        )

        return {
            "status": match_error,
            "added_tracks": [],
            "matched": 0,
            "not_found": not_found_row,
            "review": review_row,
        }

    existing_soundtrack = document.get("soundtrack") or {}

    if not isinstance(existing_soundtrack, dict):
        logger.error(
            "Unexpected soundtrack structure for %r (%s)",
            film_title,
            year,
        )

        return {
            "status": "invalid_soundtrack",
            "added_tracks": [],
            "matched": 0,
            "not_found": None,
            "review": None,
        }

    existing_tracks = existing_soundtrack.get("tracks", [])

    if not isinstance(existing_tracks, list):
        logger.error(
            "Unexpected soundtrack.tracks structure for %r (%s)",
            film_title,
            year,
        )

        return {
            "status": "invalid_tracks",
            "added_tracks": [],
            "matched": 0,
            "not_found": None,
            "review": None,
        }

    merged_tracks, added_tracks, matched_count = merge_tracks(
        existing_tracks,
        local_tracks,
    )

    updated_soundtrack = dict(existing_soundtrack)
    updated_soundtrack["folder_name"] = DEFAULT_SOUNDTRACK_NAME
    updated_soundtrack["tracks"] = merged_tracks

    local_library = updated_soundtrack.get("local_library", {})

    if not isinstance(local_library, dict):
        local_library = {}

    local_library = dict(local_library)

    for key in ("language", "language_folder", "relative_path"):
        if entry.get(key) is not None:
            local_library[key] = entry[key]

    local_library["last_scanned_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    local_library["track_count"] = len(local_tracks)
    updated_soundtrack["local_library"] = local_library

    update_fields = {
        "soundtrack": updated_soundtrack,
        "downloaded": True,
    }

    changed = any(
        document.get(key) != value
        for key, value in update_fields.items()
    )

    logger.info(
        "%s (%s): %d local tracks, %d matched, %d new",
        film_title,
        year,
        len(local_tracks),
        matched_count,
        len(added_tracks),
    )

    if not changed:
        status = "unchanged"

    elif not apply_changes:
        logger.info("[DRY RUN] Would update %r (%s)", film_title, year)
        status = "dry_run"

    else:
        collection.update_one(
            {"_id": document["_id"]},
            {"$set": update_fields},
            upsert=False,
        )

        logger.info(
            "Updated %r (%s) using MongoDB title %r",
            film_title,
            year,
            document.get("title"),
        )

        status = "updated"

    return {
        "status": status,
        "added_tracks": added_tracks,
        "matched": matched_count,
        "not_found": None,
        "review": None,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Reconcile a soundtrack manifest with MongoDB and produce "
            "CSV reports with smart title matching."
        )
    )

    parser.add_argument(
        "--manifest",
        "--input",
        dest="manifest",
        required=True,
        help="Path to the scanner's JSON manifest.",
    )

    parser.add_argument(
        "--mongo-uri",
        default=None,
        help="MongoDB URI; defaults to CINESCRAPPER_MONGO_URI.",
    )

    parser.add_argument(
        "--mongo-db",
        required=True,
        help="MongoDB database name.",
    )

    parser.add_argument(
        "--mongo-collection",
        default=DEFAULT_COLLECTION,
        help=f"MongoDB collection (default: {DEFAULT_COLLECTION}).",
    )

    parser.add_argument(
        "--report-dir",
        default="soundtrack_reports",
        help="Directory for generated CSV reports.",
    )

    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to MongoDB. Default is dry-run.",
    )

    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
        default="INFO",
    )

    return parser.parse_args()


def main():
    # Load .env when python-dotenv is installed.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    args = parse_args()
    configure_logging(args.log_level)

    mongo_uri = args.mongo_uri or os.environ.get(
        "MONGODB_URI"
    )

    if not mongo_uri:
        logger.error(
            "MongoDB URI missing. Set MONGODB_URI in .env "
            "or the environment, or pass --mongo-uri."
        )
        return 2

    try:
        entries = load_manifest(args.manifest)
    except (OSError, json.JSONDecodeError, ValueError) as exception:
        logger.error("Could not load manifest: %s", exception)
        return 2

    report_dir = Path(args.report_dir).expanduser()

    added_rows = []
    not_found_rows = []
    review_rows = []

    summary = {}

    client = None

    try:
        client = create_mongo_client(mongo_uri)
        client.admin.command("ping")

        logger.info("MongoDB connection successful.")
        logger.info("Mode: %s", "APPLY" if args.apply else "DRY RUN")
        logger.info("Manifest entries: %d", len(entries))

        collection = client[args.mongo_db][args.mongo_collection]
        catalogue = load_cinema_catalogue(collection)

        for entry in entries:
            try:
                result = reconcile_cinema(
                    collection=collection,
                    catalogue=catalogue,
                    entry=entry,
                    apply_changes=args.apply,
                )
            except Exception:
                logger.exception(
                    "Failed to reconcile %r (%s)",
                    entry.get("film_title") or entry.get("title"),
                    entry.get("year"),
                    )

                summary["processing_error"] = (
                        summary.get("processing_error", 0) + 1
                )
                continue

            status = result["status"]
            summary[status] = summary.get(status, 0) + 1

            action = "APPLIED" if args.apply else "DRY_RUN"

            added_rows.extend(
                build_added_track_rows(
                    entry,
                    result["added_tracks"],
                    action,
                )
            )

            if result["not_found"] is not None:
                not_found_rows.append(result["not_found"])

            if result["review"] is not None:
                review_rows.append(result["review"])

        write_csv(
            report_dir / "added_tracks" / "soundtrack_tracks_added.csv",
            ADDED_TRACK_FIELDS,
            added_rows,
        )

        write_csv(
            report_dir / "not_found" / "soundtrack_cinemas_not_found.csv",
            NOT_FOUND_FIELDS,
            not_found_rows,
        )

        write_csv(
            report_dir / "match_review" / "soundtrack_match_review.csv",
            MATCH_REVIEW_FIELDS,
            review_rows,
        )

        summary_rows = [
            {"metric": key, "count": value}
            for key, value in sorted(summary.items())
        ]

        summary_rows.extend([
            {
                "metric": "new_tracks_detected",
                "count": len(added_rows),
            },
            {
                "metric": "cinemas_needing_review",
                "count": len(not_found_rows),
            },
        ])

        write_csv(
            report_dir / "summary" / "soundtrack_reconciliation_summary.csv",
            ["metric", "count"],
            summary_rows,
        )

        logger.info("Reconciliation summary:")

        for key, value in sorted(summary.items()):
            logger.info("  %s: %d", key, value)

        logger.info("New tracks detected: %d", len(added_rows))
        logger.info("Cinemas needing review: %d", len(not_found_rows))
        logger.info("Match review entries: %d", len(review_rows))
        logger.info("Reports directory: %s", report_dir.resolve())

        if not args.apply:
            logger.info(
                "Dry run complete. MongoDB was not modified. "
                "Review the reports before using --apply."
            )

        return 0

    except Exception as exception:
        logger.error("MongoDB reconciliation failed: %s", exception)
        logger.debug("Failure details:", exc_info=True)
        return 1

    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    sys.exit(main())
