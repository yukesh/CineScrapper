"""Audit and optionally repair the four CineScrapper collection/download flags.

Dry-run is the default. Pass --apply to add only missing fields. Existing
values (including False) are preserved.
"""

import argparse
import os
from urllib.parse import parse_qs, urlparse

from pymongo import MongoClient


def parse_args():
    parser = argparse.ArgumentParser(
        description="Audit missing default flags in CineScrapper cinema documents."
    )
    parser.add_argument("--uri", default=os.getenv("MONGODB_URI", "mongodb://localhost:27017"), help="MongoDB connection URI.")
    parser.add_argument("--database", default=os.getenv("MONGODB_DATABASE", "cinescrapper"), help="MongoDB database name.")
    parser.add_argument("--collection", default=os.getenv("MONGODB_COLLECTION", "cinemas"), help="MongoDB collection name.")
    parser.add_argument("--apply", action="store_true", help="Write missing fields; otherwise dry-run only.")
    return parser.parse_args()


def create_mongo_client(connection_string: str) -> MongoClient:
    parsed = urlparse(connection_string)
    options = parse_qs(parsed.query)
    tls_enabled = parsed.scheme == "mongodb+srv" or any(
        value.lower() in {"true", "1", "yes"}
        for key in ("tls", "ssl") for value in options.get(key, [])
    )
    if tls_enabled:
        try:
            import certifi
        except ImportError as exc:
            raise RuntimeError("TLS MongoDB connections require certifi; install it with python -m pip install certifi") from exc
        return MongoClient(connection_string, tlsCAFile=certifi.where())
    return MongoClient(connection_string)


def audit_collection(collection, apply_changes: bool) -> dict[str, int]:
    stats = {
        "cinemas_scanned": 0, "downloaded_missing": 0,
        "cinema_add_collection_missing": 0, "soundtrack_add_collection_missing": 0,
        "tracks_scanned": 0, "track_add_collection_missing": 0,
        "documents_updated": 0,
    }
    projection = {"_id": 1, "title": 1, "year": 1, "downloaded": 1, "add_collection": 1, "soundtrack": 1}

    for cinema in collection.find({}, projection):
        stats["cinemas_scanned"] += 1
        cinema_id = cinema["_id"]
        label = f"{cinema.get('title', '<untitled>')} ({cinema.get('year', '?')})"
        missing_fields = {}
        for field in ("downloaded", "add_collection"):
            if field not in cinema:
                stat = "downloaded_missing" if field == "downloaded" else "cinema_add_collection_missing"
                stats[stat] += 1
                missing_fields[field] = False
                print(f"[MISSING] {field}: {label}, _id={cinema_id}")

        soundtrack = cinema.get("soundtrack")
        if isinstance(soundtrack, dict) and "add_collection" not in soundtrack:
            stats["soundtrack_add_collection_missing"] += 1
            print(f"[MISSING] soundtrack.add_collection: {label}, _id={cinema_id}")
            missing_fields["soundtrack.add_collection"] = False

        tracks = soundtrack.get("tracks", []) if isinstance(soundtrack, dict) else []
        missing_track_indexes = []
        if isinstance(tracks, list):
            for index, track in enumerate(tracks):
                if not isinstance(track, dict):
                    print(f"[WARNING] Invalid track structure: {label}, index={index}")
                    continue
                stats["tracks_scanned"] += 1
                if "add_collection" not in track:
                    stats["track_add_collection_missing"] += 1
                    missing_track_indexes.append(index)
                    print(f"[MISSING] soundtrack.tracks[{index}].add_collection: {label}, title={track.get('title')!r}")
        elif soundtrack is not None and isinstance(soundtrack, dict):
            print(f"[WARNING] soundtrack.tracks is not a list: {label}, _id={cinema_id}")

        if not apply_changes:
            continue

        update = {}
        for field, value in missing_fields.items():
            if field in ("downloaded", "add_collection"):
                update[field] = value
            elif field == "soundtrack.add_collection":
                update[field] = value
        if update:
            set_fields = {k: v for k, v in update.items() if "." not in k}
            set_fields.update({k: v for k, v in update.items() if "." in k})
            # Restrict to still-missing fields to avoid overwriting concurrent edits.
            conditions = {"_id": cinema_id}
            conditions.update({key: {"$exists": False} for key in update})
            result = collection.update_one(conditions, {"$set": set_fields})
            if result.modified_count:
                stats["documents_updated"] += 1

        if missing_track_indexes:
            result = collection.update_one(
                {"_id": cinema_id},
                {"$set": {"soundtrack.tracks.$[track].add_collection": False}},
                array_filters=[{"track.add_collection": {"$exists": False}}],
            )
            if result.modified_count:
                stats["documents_updated"] += 1

    return stats


def main():
    args = parse_args()
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"Database: {args.database}")
    print(f"Collection: {args.collection}\n")
    client = create_mongo_client(args.uri)
    try:
        client.admin.command("ping")
        stats = audit_collection(client[args.database][args.collection], args.apply)
    finally:
        client.close()
    print("\nAudit summary\n-------------")
    for key, value in stats.items():
        print(f"{key}: {value}")
    if not args.apply:
        print("\nDry run only; MongoDB was not modified. Use --apply to add missing fields.")


if __name__ == "__main__":
    main()
