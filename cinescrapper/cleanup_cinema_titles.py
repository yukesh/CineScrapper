"""Safely normalize existing CineScrapper cinema titles in MongoDB.

Default mode is dry-run. The only title transformations performed are:
- remove colon characters (matching the scraper's agreed title normalization)
- collapse repeated whitespace and trim leading/trailing whitespace

Documents whose proposed title would collide with another document's title/year
are reported and skipped. No fields other than `title` are modified.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pymongo import MongoClient

DEFAULT_REPORT = Path("soundtrack_reports/title_cleanup/title_cleanup_report.csv")
REPORT_FIELDS = [
    "document_id", "year", "original_title", "proposed_title", "status", "reason"
]


def normalize_title(value: str) -> str:
    """Apply only the agreed title cleanup rules; do not alter other punctuation."""
    value = value.replace(":", "")
    return re.sub(r"\s+", " ", value).strip()


def create_mongo_client(uri: str) -> MongoClient:
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
                "TLS MongoDB connections require certifi; install it with: "
                "python -m pip install certifi"
            ) from exc
        return MongoClient(uri, tlsCAFile=certifi.where())
    return MongoClient(uri)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit and optionally clean existing CineScrapper cinema titles."
    )
    parser.add_argument(
        "--uri",
        default=os.getenv("MONGODB_URI") or os.getenv("CINESCRAPPER_MONGO_URI")
        or "mongodb://localhost:27017",
        help="MongoDB URI (default: MONGODB_URI, CINESCRAPPER_MONGO_URI, or localhost).",
    )
    parser.add_argument("--database", default=os.getenv("MONGODB_DATABASE", "cinescrapper"))
    parser.add_argument("--collection", default=os.getenv("MONGODB_COLLECTION", "cinemas"))
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT,
                        help=f"CSV report path (default: {DEFAULT_REPORT}).")
    parser.add_argument("--apply", action="store_true",
                        help="Write safe title changes. Without this flag, dry-run only.")
    return parser.parse_args()


def audit_and_clean(collection, apply_changes: bool) -> tuple[dict[str, int], list[dict[str, str]]]:
    documents = list(collection.find({}, {"_id": 1, "title": 1, "year": 1}))

    # Build normalized title/year ownership so we can avoid introducing collisions.
    normalized_owners: dict[tuple[str, str], list[object]] = {}
    for doc in documents:
        title = doc.get("title")
        if isinstance(title, str):
            key = (normalize_title(title).casefold(), str(doc.get("year", "")))
            normalized_owners.setdefault(key, []).append(doc["_id"])

    stats = {
        "documents_scanned": len(documents),
        "titles_needing_cleanup": 0,
        "changes_applied": 0,
        "collision_skipped": 0,
        "invalid_titles": 0,
        "unchanged": 0,
    }
    rows: list[dict[str, str]] = []

    for doc in documents:
        old = doc.get("title")
        year = doc.get("year", "")
        doc_id = str(doc.get("_id", ""))
        if not isinstance(old, str) or not old.strip():
            stats["invalid_titles"] += 1
            rows.append({"document_id": doc_id, "year": str(year),
                         "original_title": repr(old), "proposed_title": "",
                         "status": "SKIPPED_INVALID_TITLE", "reason": "title is missing, empty, or not a string"})
            print(f"[WARNING] Skipping invalid title: _id={doc_id}, title={old!r}")
            continue

        new = normalize_title(old)
        if new == old:
            stats["unchanged"] += 1
            continue

        stats["titles_needing_cleanup"] += 1
        key = (new.casefold(), str(year))
        other_ids = [owner for owner in normalized_owners.get(key, []) if owner != doc["_id"]]
        if other_ids:
            stats["collision_skipped"] += 1
            status = "SKIPPED_COLLISION"
            reason = "another document has the same normalized title and year: " + ",".join(map(str, other_ids))
            print(f"[WARNING] Title collision; not changing {old!r} ({year}) -> {new!r}; _id={doc_id}; conflicts={other_ids}")
        elif apply_changes:
            result = collection.update_one(
                {"_id": doc["_id"], "title": old},
                {"$set": {"title": new}},
            )
            if result.modified_count:
                stats["changes_applied"] += 1
                status, reason = "APPLIED", "title updated"
                print(f"[UPDATED] {old!r} -> {new!r} ({year}), _id={doc_id}")
            else:
                status, reason = "SKIPPED_CONCURRENT_CHANGE", "document changed before update; re-run audit"
                print(f"[WARNING] Concurrent change; not updated _id={doc_id}")
        else:
            status, reason = "WOULD_UPDATE", "dry-run; MongoDB not modified"
            print(f"[WOULD UPDATE] {old!r} -> {new!r} ({year}), _id={doc_id}")

        rows.append({"document_id": doc_id, "year": str(year), "original_title": old,
                     "proposed_title": new, "status": status, "reason": reason})

    return stats, rows


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    args = parse_args()
    print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
    print(f"Database: {args.database}")
    print(f"Collection: {args.collection}\n")

    client = create_mongo_client(args.uri)
    try:
        client.admin.command("ping")
        stats, rows = audit_and_clean(client[args.database][args.collection], args.apply)
    finally:
        client.close()

    args.report.parent.mkdir(parents=True, exist_ok=True)
    with args.report.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=REPORT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print("\nTitle cleanup summary\n---------------------")
    for name, value in stats.items():
        print(f"{name}: {value}")
    print(f"Report: {args.report}")
    if not args.apply:
        print("\nDry run only; MongoDB was not modified. Review the CSV, then use --apply to write changes.")


if __name__ == "__main__":
    main()
