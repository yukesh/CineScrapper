"""Audit and optionally repair default fields in CineScrapper MongoDB documents.

Dry-run is the default. Pass --apply to write missing fields.

Checks:
- Cinema-level downloaded: False
- Track-level soundtrack.tracks[].add_collection: False

Existing values are preserved. A CSV report is written under
soundtrack_reports/audit/ by default.
"""

import argparse
import csv
import os
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pymongo import MongoClient


DEFAULT_REPORT_DIR = Path("soundtrack_reports/audit")
REPORT_FIELDS = [
    "document_id",
    "title",
    "year",
    "field",
    "track_index",
    "track_title",
    "current_value",
    "proposed_value",
    "status",
]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Audit missing default fields in CineScrapper cinema documents."
    )
    parser.add_argument(
        "--uri",
        default=(os.getenv("MONGODB_URI") or os.getenv("CINESCRAPPER_MONGO_URI") or "mongodb://localhost:27017"),
        help="MongoDB connection URI.",
    )
    parser.add_argument(
        "--database",
        default=os.getenv("MONGODB_DATABASE", "cinescrapper"),
        help="MongoDB database name.",
    )
    parser.add_argument(
        "--collection",
        default=os.getenv("MONGODB_COLLECTION", "cinemas"),
        help="MongoDB collection name.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=DEFAULT_REPORT_DIR,
        help="Directory for the audit CSV report (default: soundtrack_reports/audit).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write missing fields. Without this option, run in dry-run mode.",
    )
    return parser.parse_args()


def create_mongo_client(connection_string: str) -> MongoClient:
    """Create a MongoDB client with CA verification enabled for TLS."""
    parsed = urlparse(connection_string)
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
                "TLS MongoDB connections require certifi. "
                "Install it with: python -m pip install certifi"
            ) from exc

        return MongoClient(connection_string, tlsCAFile=certifi.where())

    return MongoClient(connection_string)


def is_missing(document: dict, field: str) -> bool:
    """True only when a field is absent; False and None count as present."""
    return field not in document


def _report_row(cinema, field, track_index="", track_title=""):
    return {
        "document_id": str(cinema.get("_id", "")),
        "title": cinema.get("title", "<untitled>"),
        "year": cinema.get("year", "?"),
        "field": field,
        "track_index": track_index,
        "track_title": track_title,
        "current_value": "<missing>",
        "proposed_value": "False",
        "status": "MISSING",
    }


def audit_collection(collection, apply_changes: bool) -> tuple[dict, list[dict]]:
    stats = {
        "cinemas_scanned": 0,
        "downloaded_missing": 0,
        "tracks_scanned": 0,
        "add_collection_missing": 0,
        "documents_updated": 0,
    }
    report_rows = []

    projection = {
        "_id": 1,
        "title": 1,
        "year": 1,
        "downloaded": 1,
        "soundtrack": 1,
    }

    for cinema in collection.find({}, projection):
        stats["cinemas_scanned"] += 1
        cinema_id = cinema["_id"]
        title = cinema.get("title", "<untitled>")
        year = cinema.get("year", "?")
        missing_downloaded = is_missing(cinema, "downloaded")
        missing_track_indexes = []

        if missing_downloaded:
            stats["downloaded_missing"] += 1
            report_rows.append(_report_row(cinema, "downloaded"))
            print(f"[MISSING] downloaded: {title} ({year}), _id={cinema_id}")

        soundtrack = cinema.get("soundtrack")
        tracks = soundtrack.get("tracks", []) if isinstance(soundtrack, dict) else []

        if isinstance(tracks, list):
            for index, track in enumerate(tracks):
                if not isinstance(track, dict):
                    print(
                        f"[WARNING] Invalid track structure: {title} ({year}), "
                        f"track index {index}"
                    )
                    continue

                stats["tracks_scanned"] += 1
                if is_missing(track, "add_collection"):
                    stats["add_collection_missing"] += 1
                    missing_track_indexes.append(index)
                    report_rows.append(
                        _report_row(
                            cinema,
                            "soundtrack.tracks[].add_collection",
                            track_index=index,
                            track_title=track.get("title") or track.get("name") or "",
                        )
                    )
                    print(
                        f"[MISSING] add_collection: {title} ({year}), "
                        f"track index {index}, title={track.get('title')!r}"
                    )
        elif soundtrack is not None:
            print(
                f"[WARNING] soundtrack.tracks is not a list: "
                f"{title} ({year}), _id={cinema_id}"
            )

        if not apply_changes:
            continue

        document_updated = False
        if missing_downloaded:
            result = collection.update_one(
                {"_id": cinema_id, "downloaded": {"$exists": False}},
                {"$set": {"downloaded": False}},
            )
            if result.modified_count:
                document_updated = True
                for row in report_rows:
                    if row["document_id"] == str(cinema_id) and row["field"] == "downloaded":
                        row["status"] = "APPLIED"

        if missing_track_indexes:
            result = collection.update_one(
                {"_id": cinema_id},
                {"$set": {"soundtrack.tracks.$[track].add_collection": False}},
                array_filters=[{"track.add_collection": {"$exists": False}}],
            )
            if result.modified_count:
                document_updated = True
                for row in report_rows:
                    if (
                        row["document_id"] == str(cinema_id)
                        and row["field"] == "soundtrack.tracks[].add_collection"
                        and row["track_index"] in missing_track_indexes
                    ):
                        row["status"] = "APPLIED"

        if document_updated:
            stats["documents_updated"] += 1

    return stats, report_rows


def write_report(report_dir: Path, rows: list[dict]) -> Path:
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "missing_fields_audit.csv"
    with report_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return report_path


def main():
    # Load project .env when python-dotenv is installed, before reading defaults.
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    args = parse_args()

    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"Database: {args.database}")
    print(f"Collection: {args.collection}")
    print()

    client = create_mongo_client(args.uri)
    try:
        client.admin.command("ping")
        collection = client[args.database][args.collection]
        stats, report_rows = audit_collection(collection, apply_changes=args.apply)
    finally:
        client.close()

    report_path = write_report(args.report_dir, report_rows)

    print()
    print("Audit summary")
    print("-------------")
    for key, value in stats.items():
        print(f"{key}: {value}")
    print(f"Report: {report_path}")

    if not args.apply:
        print()
        print("Dry run only; MongoDB was not modified.")
        print("Use --apply to write the missing fields.")


if __name__ == "__main__":
    main()
