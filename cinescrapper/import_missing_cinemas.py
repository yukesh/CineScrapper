"""Import manually approved missing cinema documents into MongoDB.

The default mode is a dry run. Edit the JSON created by export_missing_cinemas
and set status to "approved" only for entries you have reviewed. Then pass
--apply to insert those entries. Possible matches are intentionally not imported
by this script; review them separately to avoid duplicate cinema records.
"""
from __future__ import annotations

from cinescrapper.env import load_project_env

load_project_env()


import argparse
import json
import logging
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

LOGGER = logging.getLogger("cinescrapper.import_missing_cinemas")


def normalize_title(title: object) -> str:
    """Normalize a title for comparison without changing its stored value."""
    if not isinstance(title, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "", title.casefold())


def create_mongo_client(uri: str):
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
                "TLS MongoDB connections require certifi; install it with "
                "python -m pip install certifi"
            ) from exc
        return MongoClient(uri, tlsCAFile=certifi.where())
    return MongoClient(uri)


def prepare_cinema(raw: dict) -> dict:
    """Prepare a reviewed export item with default flags and no report metadata."""
    cinema = dict(raw)
    cinema.pop("_id", None)
    cinema.pop("status", None)
    cinema.setdefault("downloaded", False)
    cinema.setdefault("add_collection", False)

    soundtrack = cinema.get("soundtrack")
    if isinstance(soundtrack, dict):
        soundtrack = dict(soundtrack)
        soundtrack.setdefault("add_collection", False)
        tracks = soundtrack.get("tracks", [])
        if isinstance(tracks, list):
            soundtrack["tracks"] = [
                {**track, "add_collection": track.get("add_collection", False)}
                if isinstance(track, dict) else track
                for track in tracks
            ]
        cinema["soundtrack"] = soundtrack
    return cinema


def parse_args():
    parser = argparse.ArgumentParser(
        description="Dry-run or import manually approved missing cinema documents."
    )
    parser.add_argument("--input", type=Path, default=Path("reports/missing_cinemas.json"))
    parser.add_argument("--uri", default=None, help="MongoDB URI; defaults to MONGODB_URI/CINESCRAPPER_MONGO_URI.")
    parser.add_argument("--database", default=None)
    parser.add_argument("--collection", default=None)
    parser.add_argument("--apply", action="store_true", help="Actually insert approved documents; default is dry-run.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def load_approved(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("Input must be a JSON array produced by export_missing_cinemas.py")
    approved = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            LOGGER.warning("Skipping item %d: expected an object", index)
            continue
        if item.get("status") != "approved":
            LOGGER.info("Skipping item %d (%s): status is not 'approved'", index, item.get("title", "untitled"))
            continue
        approved.append(prepare_cinema(item))
    return approved


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
    if not args.input.is_file():
        LOGGER.error("Input file does not exist: %s", args.input)
        return 2

    try:
        approved = load_approved(args.input)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        LOGGER.error("Unable to read approved entries: %s", exc)
        return 2

    uri = args.uri or os.getenv("CINESCRAPPER_MONGO_URI") or os.getenv("MONGODB_URI") or "mongodb://localhost:27017"
    database = args.database or os.getenv("CINESCRAPPER_MONGODB_DATABASE") or os.getenv("MONGODB_DATABASE") or "cinescrapper"
    collection_name = args.collection or os.getenv("CINESCRAPPER_MONGODB_COLLECTION") or os.getenv("MONGODB_COLLECTION") or "cinemas"

    LOGGER.info("Mode: %s", "APPLY" if args.apply else "DRY RUN")
    LOGGER.info("Approved entries loaded: %d", len(approved))
    client = None
    inserted = skipped = errors = 0
    try:
        client = create_mongo_client(uri)
        client.admin.command("ping")
        collection = client[database][collection_name]

        # Cache existing titles by year; refresh after each insert.
        existing_by_year: dict[int, set[str]] = {}
        for doc in collection.find({}, {"_id": 0, "title": 1, "year": 1}):
            try:
                year = int(doc["year"])
            except (KeyError, TypeError, ValueError):
                continue
            existing_by_year.setdefault(year, set()).add(normalize_title(doc.get("title")))

        for cinema in approved:
            title = cinema.get("title")
            try:
                year = int(cinema.get("year"))
            except (TypeError, ValueError):
                LOGGER.error("Skipping entry with invalid year: %r", title)
                errors += 1
                continue
            normalized = normalize_title(title)
            if not normalized:
                LOGGER.error("Skipping entry with missing/invalid title for year %s", year)
                errors += 1
                continue
            if normalized in existing_by_year.get(year, set()):
                LOGGER.warning("Skipping duplicate title/year: %s (%s)", title, year)
                skipped += 1
                continue

            if args.apply:
                try:
                    collection.insert_one(cinema)
                except Exception:
                    LOGGER.exception("Insert failed for %s (%s)", title, year)
                    errors += 1
                    continue
            else:
                LOGGER.info("Would insert: %s (%s)", title, year)
            inserted += 1
            existing_by_year.setdefault(year, set()).add(normalized)

    except Exception:
        LOGGER.exception("MongoDB import failed")
        return 1
    finally:
        if client is not None:
            client.close()

    LOGGER.info("Summary: %s=%d, skipped_duplicates=%d, errors=%d", "inserted" if args.apply else "would_insert", inserted, skipped, errors)
    if not args.apply:
        LOGGER.info("Dry run only; MongoDB was not modified. Use --apply after reviewing the output.")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
