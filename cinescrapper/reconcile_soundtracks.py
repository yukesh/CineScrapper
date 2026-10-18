
#!/usr/bin/env python3
"""Reconcile an OST-only library manifest with CineScrapper MongoDB.

Dry-run is the default. Use --apply to write changes.

Existing track metadata and add_collection flags are preserved.
New tracks default add_collection to False. Track paths are stored
relative to the language library root.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def norm(value: str | None) -> str:
    """Normalise a string for punctuation- and case-insensitive comparison."""
    return re.sub(r"[^a-z0-9]+", "", (value or "").casefold())


def title_query(title: str, year: int | None) -> dict:
    if year is not None:
        return {"title": title, "year": year}

    return {"title": title}


def local_track_title(filename: str) -> str:
    return Path(filename).stem


def merge_local_tracks(
        existing_tracks: list,
        local_tracks: list,
) -> list:
    """Merge scanned tracks while preserving existing metadata and flags."""
    tracks = [
        dict(track)
        for track in existing_tracks
        if isinstance(track, dict)
    ]

    by_title: dict[str, list[dict]] = {}

    for track in tracks:
        key = norm(track.get("title"))

        if key:
            by_title.setdefault(key, []).append(track)

    for local_track in local_tracks:
        filename = local_track.get("filename")

        if not filename:
            logger.warning(
                "Skipping manifest track without a filename: %r",
                local_track,
            )
            continue

        title = local_track_title(filename)
        key = norm(title)
        matches = by_title.get(key, [])

        if len(matches) > 1:
            raise ValueError(
                f"Ambiguous existing track title {title!r}: "
                f"{len(matches)} tracks have equivalent normalised titles"
            )

        if matches:
            track = matches[0]

            # Preserve the user's existing choice.
            track.setdefault("add_collection", False)

            # Update the path to the currently scanned location.
            relative_path = local_track.get("relative_path")

            if relative_path:
                track["relative_path"] = relative_path

            continue

        max_number = max(
            (
                track["number"]
                for track in tracks
                if isinstance(track.get("number"), int)
                   and not isinstance(track.get("number"), bool)
            ),
            default=0,
        )

        new_track = {
            "number": max_number + 1,
            "title": title,
            "lyrics": None,
            "singers": None,
            "length": None,
            "add_collection": False,
        }

        relative_path = local_track.get("relative_path")

        if relative_path:
            new_track["relative_path"] = relative_path

        tracks.append(new_track)
        by_title.setdefault(key, []).append(new_track)

    for track in tracks:
        track.setdefault("add_collection", False)

    return tracks


def choose_document(collection, item: dict):
    """Find exactly one cinema document; never guess between matches."""
    query = title_query(
        item["film_title"],
        item.get("year"),
    )

    try:
        matches = list(collection.find(query).limit(2))
    except Exception:
        logger.exception(
            "MongoDB query failed for cinema %r [%s]",
            item.get("film_title"),
            item.get("year"),
        )
        return None, "MongoDB query failed"

    if len(matches) == 1:
        return matches[0], None

    if len(matches) > 1:
        logger.error(
            "Ambiguous exact MongoDB match: title=%r, year=%r",
            item["film_title"],
            item.get("year"),
        )
        return None, "ambiguous cinema match"

    # Fallback for title punctuation/case differences.
    try:
        if item.get("year") is not None:
            candidates = list(
                collection.find({"year": item["year"]})
            )
        else:
            candidates = list(
                collection.find({"title": {"$exists": True}})
            )
    except Exception:
        logger.exception(
            "MongoDB fallback query failed for cinema %r [%s]",
            item.get("film_title"),
            item.get("year"),
        )
        return None, "MongoDB fallback query failed"

    candidates = [
        document
        for document in candidates
        if norm(document.get("title")) == norm(item["film_title"])
    ]

    if len(candidates) == 1:
        logger.warning(
            "Cinema matched using normalised title fallback: %r [%s]",
            item["film_title"],
            item.get("year"),
        )
        return candidates[0], None

    if not candidates:
        logger.error(
            "Cinema not found in MongoDB: title=%r, year=%r",
            item["film_title"],
            item.get("year"),
        )
        return None, "no matching cinema document"

    logger.error(
        "Ambiguous normalised MongoDB match: title=%r, year=%r, matches=%d",
        item["film_title"],
        item.get("year"),
        len(candidates),
    )
    return None, "ambiguous cinema match"


def reconcile_one(
        collection,
        item: dict,
        apply: bool = False,
) -> str:
    """Reconcile one OST manifest item with one cinema document."""
    document, issue = choose_document(collection, item)

    if issue:
        logger.warning(
            "Skipping %s [%s]: %s",
            item.get("film_title"),
            item.get("year"),
            issue,
        )
        return issue

    soundtrack = document.get("soundtrack")
    folder_name = item["soundtrack_folder_name"]

    if not isinstance(soundtrack, dict):
        soundtrack = {
            "album_name": folder_name,
            "composer": None,
            "ref": None,
            "tracks": [],
        }
    else:
        album_name = soundtrack.get("album_name")

        if album_name and norm(album_name) != norm(folder_name):
            logger.error(
                "Soundtrack mismatch for %s [%s]: "
                "MongoDB album_name=%r, scanned=%r. Skipping update.",
                item["film_title"],
                item.get("year"),
                album_name,
                folder_name,
            )
            return (
                f"soundtrack folder mismatch: "
                f"MongoDB album_name={album_name!r}, "
                f"folder={folder_name!r}"
            )

        if not album_name:
            soundtrack["album_name"] = folder_name

    try:
        soundtrack["tracks"] = merge_local_tracks(
            soundtrack.get("tracks", []),
            item.get("tracks", []),
        )
    except ValueError as exc:
        logger.error(
            "Track reconciliation failed for %s [%s]: %s",
            item["film_title"],
            item.get("year"),
            exc,
        )
        return f"track reconciliation error: {exc}"

    soundtrack["local_library"] = {
        "language": item["language"],
        "language_folder": item["language_folder"],
        "relative_path": item["relative_path"],
        "last_scanned_at": datetime.now(timezone.utc).isoformat(),
        "track_count": len(item.get("tracks", [])),
    }

    if not apply:
        logger.info(
            "DRY RUN: would update OST for %s [%s] (%d scanned tracks)",
            item["film_title"],
            item.get("year"),
            len(item.get("tracks", [])),
        )
        return "would update"

    try:
        result = collection.update_one(
            {"_id": document["_id"]},
            {"$set": {"soundtrack": soundtrack}},
        )
    except Exception:
        logger.exception(
            "MongoDB update failed for %s [%s]",
            item["film_title"],
            item.get("year"),
        )
        return "MongoDB update failed"

    if result.modified_count:
        logger.info(
            "Updated OST for %s [%s]",
            item["film_title"],
            item.get("year"),
        )
        return "updated"

    logger.info(
        "No MongoDB changes required for %s [%s]",
        item["film_title"],
        item.get("year"),
    )
    return "unchanged"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--input",
        required=True,
        help="JSON manifest produced by scan_library.py",
    )
    parser.add_argument(
        "--mongo-uri",
        default=None,
        help="MongoDB URI; defaults to CINESCRAPPER_MONGO_URI",
    )
    parser.add_argument(
        "--mongo-db",
        required=True,
        help="MongoDB database name",
    )
    parser.add_argument(
        "--mongo-collection",
        default="cinema",
        help="MongoDB collection name (default: cinema)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write changes to MongoDB; otherwise run in dry-run mode",
    )

    args = parser.parse_args()

    input_path = Path(args.input)

    try:
        manifest = json.loads(
            input_path.read_text(encoding="utf-8")
        )
    except FileNotFoundError:
        logger.error("Manifest file not found: %s", input_path)
        return 2
    except json.JSONDecodeError:
        logger.exception("Manifest contains invalid JSON: %s", input_path)
        return 2
    except OSError:
        logger.exception("Unable to read manifest: %s", input_path)
        return 2

    if not isinstance(manifest, dict) or not isinstance(
            manifest.get("items"), list
    ):
        logger.error(
            "Invalid manifest: expected a JSON object containing an items list"
        )
        return 2

    uri = args.mongo_uri or os.environ.get("CINESCRAPPER_MONGO_URI")

    if not uri:
        parser.error(
            "Provide --mongo-uri or set CINESCRAPPER_MONGO_URI"
        )

    try:
        from pymongo import MongoClient
    except ImportError:
        logger.error(
            "Missing dependency. Install it with: "
            "python -m pip install pymongo"
        )
        return 2

    client = None
    counts: dict[str, int] = {}

    try:
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
        )

        # Force a connection check so unreachable MongoDB is reported early.
        client.admin.command("ping")

        collection = client[args.mongo_db][args.mongo_collection]

        logger.info(
            "Starting %s reconciliation: database=%s, collection=%s, items=%d",
            "APPLY" if args.apply else "DRY RUN",
            args.mongo_db,
            args.mongo_collection,
            len(manifest["items"]),
        )

        for index, item in enumerate(manifest["items"], start=1):
            if not isinstance(item, dict):
                logger.error(
                    "Skipping malformed manifest item at index %d: expected object",
                    index - 1,
                    )
                counts["invalid manifest item"] = (
                        counts.get("invalid manifest item", 0) + 1
                )
                continue

            required_fields = {
                "film_title",
                "soundtrack_folder_name",
                "language",
                "language_folder",
                "relative_path",
                "tracks",
            }

            missing = sorted(required_fields - item.keys())

            if missing:
                logger.error(
                    "Skipping manifest item %d; missing fields: %s",
                    index - 1,
                    ", ".join(missing),
                    )
                counts["invalid manifest item"] = (
                        counts.get("invalid manifest item", 0) + 1
                )
                continue

            if item["soundtrack_folder_name"] != "Original Soundtrack":
                logger.warning(
                    "Skipping non-OST manifest item: %s [%s] / %s",
                    item.get("film_title"),
                    item.get("year"),
                    item.get("soundtrack_folder_name"),
                )
                counts["non-OST skipped"] = (
                        counts.get("non-OST skipped", 0) + 1
                )
                continue

            if not isinstance(item["tracks"], list):
                logger.error(
                    "Skipping %s [%s]: tracks must be a list",
                    item.get("film_title"),
                    item.get("year"),
                )
                counts["invalid manifest item"] = (
                        counts.get("invalid manifest item", 0) + 1
                )
                continue

            status = reconcile_one(
                collection,
                item,
                apply=args.apply,
            )
            counts[status] = counts.get(status, 0) + 1

    except Exception:
        logger.exception("Reconciliation stopped due to an unexpected failure")
        return 1
    finally:
        if client is not None:
            client.close()

    logger.info(
        "%s reconciliation finished. Results: %s",
        "APPLIED" if args.apply else "DRY RUN",
        ", ".join(
            f"{status}={count}"
            for status, count in sorted(counts.items())
        ) or "no items processed",
        )

    failures = sum(
        count
        for status, count in counts.items()
        if status not in {"updated", "unchanged", "would update"}
    )

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
