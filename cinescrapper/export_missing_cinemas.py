
"""Export cinema records missing from MongoDB without modifying the database."""

from __future__ import annotations

from cinescrapper.env import load_project_env

load_project_env()


import argparse
import difflib
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

from cinescrapper.config import ScraperConfig
from cinescrapper.rate_limiter import RateLimiter
from cinescrapper.scrapper import discover_movies
from cinescrapper.wiki_client import WikiClient


LOGGER = logging.getLogger("cinescrapper.export_missing_cinemas")

DEFAULT_MASTER_PAGE = "Lists_of_Tamil-language_films"
DEFAULT_DATABASE = "cinescrapper"
DEFAULT_COLLECTION = "cinemas"
FUZZY_MATCH_THRESHOLD = 0.86


def normalize_title(title: str | None) -> str:
    """Normalize a title for comparison only; never change the stored title."""
    if not isinstance(title, str):
        return ""

    return re.sub(r"[^a-z0-9]+", "", title.casefold())


def create_mongo_client(uri: str):
    """Create a MongoDB client, supporting TLS connections."""
    from pymongo import MongoClient

    parsed = urlparse(uri)
    options = parse_qs(parsed.query)

    tls_enabled = parsed.scheme == "mongodb+srv" or any(
        value.lower() in {"true", "1", "yes"}
        for key in ("tls", "ssl")
        for value in options.get(key, [])
    )

    if tls_enabled:
        try:
            import certifi
        except ImportError as exc:
            raise RuntimeError(
                "TLS connections require certifi. Install it with "
                "'python -m pip install certifi'."
            ) from exc

        return MongoClient(uri, tlsCAFile=certifi.where())

    return MongoClient(uri)


def absolute_wikipedia_url(ref: str | None) -> str | None:
    """Convert relative Wikipedia references to absolute URLs."""
    if not ref:
        return ref

    if ref.startswith("//"):
        return "https:" + ref

    if ref.startswith("/"):
        return urljoin("https://en.wikipedia.org", ref)

    return ref


def cinema_to_mongo_shape(cinema) -> dict:
    """Serialize CineInfo using the existing MongoDB document shape."""
    document = cinema.to_dict()

    document["ref"] = absolute_wikipedia_url(document.get("ref"))

    # These fields are not part of CineInfo, so add them only to the export.
    document.setdefault("downloaded", False)
    document.setdefault("add_collection", False)

    soundtrack = document.get("soundtrack")
    if not isinstance(soundtrack, dict):
        soundtrack = {
            "album_name": None,
            "composer": None,
            "ref": None,
            "tracks": [],
        }

    soundtrack.setdefault("album_name", None)
    soundtrack.setdefault("composer", None)
    soundtrack.setdefault("ref", None)
    soundtrack.setdefault("tracks", [])
    soundtrack.setdefault("add_collection", False)

    # New track selections default to False; preserve any existing value.
    if isinstance(soundtrack["tracks"], list):
        soundtrack["tracks"] = [
            {**track, "add_collection": track.get("add_collection", False)}
            if isinstance(track, dict) else track
            for track in soundtrack["tracks"]
        ]

    document["soundtrack"] = soundtrack
    document.setdefault("source", [])
    document.setdefault("cast", [])
    document.setdefault("director", None)
    document.setdefault("studio", None)

    return document


def find_title_matches(
        title: str,
        year: int,
        existing_by_year: dict[int, list[dict]],
    threshold: float = FUZZY_MATCH_THRESHOLD,
) -> list[dict]:
    """Find likely existing titles for the same year."""
    normalized = normalize_title(title)
    if not normalized:
        return []

    matches = []

    for existing in existing_by_year.get(year, []):
        existing_title = existing.get("title")
        candidate = normalize_title(existing_title)

        if not candidate:
            continue

        score = difflib.SequenceMatcher(
            None, normalized, candidate
        ).ratio()

        if score >= threshold:
            matches.append({
                "title": existing_title,
                "year": existing.get("year"),
                "similarity": round(score, 4),
            })

    return sorted(
        matches,
        key=lambda item: item["similarity"],
        reverse=True,
    )


def write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)

        # End the file with a newline for convenient command-line use.
        handle.write("\n")


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Discover Wikipedia cinema entries over a year range, "
            "compare them with MongoDB, and export missing entries. "
            "MongoDB is read-only in this script."
        )
    )

    parser.add_argument(
        "--start-year",
        type=int,
        required=True,
        help="First year to scan, inclusive.",
    )
    parser.add_argument(
        "--end-year",
        type=int,
        required=True,
        help="Last year to scan, inclusive.",
    )
    parser.add_argument(
        "--master-page",
        default=DEFAULT_MASTER_PAGE,
        help=f"Wikipedia master list page (default: {DEFAULT_MASTER_PAGE}).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output JSON path for missing cinema documents.",
    )
    parser.add_argument(
        "--uri",
        default=None,
        help="MongoDB URI; defaults to MONGODB_URI/CINESCRAPPER_MONGO_URI.",
    )
    parser.add_argument(
        "--database",
        default=None,
        help="MongoDB database (default: MONGODB_DATABASE or cinescrapper).",
    )
    parser.add_argument(
        "--collection",
        default=None,
        help="MongoDB collection (default: MONGODB_COLLECTION or cinemas).",
    )
    parser.add_argument(
        "--fuzzy-threshold",
        type=float,
        default=FUZZY_MATCH_THRESHOLD,
        help="Similarity threshold for possible matches (0 to 1).",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity.",
    )

    return parser.parse_args()


def main() -> int:
    try:
        load_project_env()
    except ImportError:
        pass

    args = parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )

    if args.start_year > args.end_year:
        LOGGER.error("--start-year must be less than or equal to --end-year")
        return 2

    if not 0.0 <= args.fuzzy_threshold <= 1.0:
        LOGGER.error("--fuzzy-threshold must be between 0 and 1")
        return 2

    args.fuzzy_threshold = args.fuzzy_threshold

    uri = (
            args.uri
            or os.getenv("MONGODB_URI")
            or os.getenv("CINESCRAPPER_MONGO_URI")
            or "mongodb://localhost:27017"
    )
    database_name = (
            args.database
            or os.getenv("MONGODB_DATABASE")
            or DEFAULT_DATABASE
    )
    collection_name = (
            args.collection
            or os.getenv("MONGODB_COLLECTION")
            or DEFAULT_COLLECTION
    )

    output_path = args.output or Path(
        f"reports/missing_cinemas_{args.start_year}_{args.end_year}.json"
    )
    possible_path = output_path.with_name(
        f"possible_matches_{args.start_year}_{args.end_year}.json"
    )
    summary_path = output_path.with_name(
        f"audit_summary_{args.start_year}_{args.end_year}.json"
    )

    client = None

    try:
        LOGGER.info(
            "Connecting to MongoDB database=%s collection=%s",
            database_name,
            collection_name,
        )

        client = create_mongo_client(uri)
        client.admin.command("ping")

        collection = client[database_name][collection_name]

        existing_documents = list(
            collection.find(
                {},
                {"_id": 0, "title": 1, "year": 1},
            )
        )

        existing_by_year: dict[int, list[dict]] = {}

        for document in existing_documents:
            try:
                year = int(document["year"])
            except (KeyError, TypeError, ValueError):
                continue

            existing_by_year.setdefault(year, []).append(document)

        LOGGER.info(
            "Loaded %d existing cinema records for comparison",
            len(existing_documents),
        )

        config = ScraperConfig.from_env()
        config.validate()

        wiki_client = WikiClient(
            rate_limiter=RateLimiter(
                config.wiki_rate_limit,
                config.rate_limit_jitter,
            ),
            max_retries=config.max_retries,
            timeout=config.request_timeout,
            cache_ttl_seconds=config.cache_ttl_seconds,
        )

        missing_cinemas = []
        possible_matches = []
        failed_years = []
        years_processed = 0
        total_discovered = 0
        exact_matches = 0

        # Keep one WikiClient for the whole run to reuse its session and cache.
        for year in range(args.start_year, args.end_year + 1):
            LOGGER.info("Discovering films for %d", year)

            try:
                movies = discover_movies(
                    args.master_page,
                    year,
                    wiki_client,
                )
            except Exception as exc:
                LOGGER.exception("Discovery failed for year %d", year)
                failed_years.append({
                    "year": year,
                    "reason": str(exc),
                })
                continue

            if not movies:
                # Do not claim this year is complete or mark it as missing.
                LOGGER.warning(
                    "No films discovered for %d; flagging year for review",
                    year,
                )
                failed_years.append({
                    "year": year,
                    "reason": (
                        "No films discovered. Check the Wikipedia page, "
                        "master-list links, cache, or parser output."
                    ),
                })
                continue

            years_processed += 1
            total_discovered += len(movies)

            seen_in_year = set()

            for movie in movies:
                if not movie.title or movie.year is None:
                    LOGGER.warning(
                        "Skipping entry with missing title/year: %s",
                        movie,
                    )
                    continue

                movie_year = int(movie.year)

                # Avoid duplicate rows from multiple tables on the same page.
                dedupe_key = (
                    normalize_title(movie.title),
                    movie_year,
                )
                if dedupe_key in seen_in_year:
                    continue
                seen_in_year.add(dedupe_key)

                normalized_title = normalize_title(movie.title)

                exact_match = any(
                    normalize_title(existing.get("title")) == normalized_title
                    for existing in existing_by_year.get(movie_year, [])
                )

                if exact_match:
                    exact_matches += 1
                    continue

                matches = find_title_matches(
                    movie.title,
                    movie_year,
                    existing_by_year,
                    threshold=args.fuzzy_threshold,
                )

                document = cinema_to_mongo_shape(movie)
                document["status"] = "review"

                if matches:
                    possible_matches.append({
                        "cinema": document,
                        "possible_database_matches": matches,
                    })
                else:
                    missing_cinemas.append(document)

            LOGGER.info(
                "Year %d complete: discovered %d rows",
                year,
                len(movies),
            )

        # The report is audit-only. No inserts, updates or deletes are performed.
        summary = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "start_year": args.start_year,
            "end_year": args.end_year,
            "master_page": args.master_page,
            "database": database_name,
            "collection": collection_name,
            "mongo_documents_checked": len(existing_documents),
            "years_requested": args.end_year - args.start_year + 1,
            "years_processed": years_processed,
            "failed_or_empty_years": failed_years,
            "discovered_rows": total_discovered,
            "exact_matches": exact_matches,
            "missing_count": len(missing_cinemas),
            "possible_match_count": len(possible_matches),
            "fuzzy_match_threshold": args.fuzzy_threshold,
            "mongo_modified": False,
        }

        write_json(output_path, missing_cinemas)
        write_json(possible_path, possible_matches)
        write_json(summary_path, summary)

        LOGGER.info("Audit finished")
        LOGGER.info("Missing cinemas: %d", len(missing_cinemas))
        LOGGER.info("Possible matches: %d", len(possible_matches))
        LOGGER.info("Years needing review: %d", len(failed_years))
        LOGGER.info("Missing JSON: %s", output_path)
        LOGGER.info("Possible matches JSON: %s", possible_path)
        LOGGER.info("Summary JSON: %s", summary_path)
        LOGGER.info("MongoDB was not modified.")

        return 0

    except Exception:
        LOGGER.exception("Cinema audit failed")
        return 1

    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
