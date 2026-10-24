#!/usr/bin/env python3
"""Insert approved local-only cinemas into MongoDB, with their local soundtrack tracks.

Dry-run is the default. Only entries whose status is exactly "approved" are
considered. Existing cinema documents and soundtrack_wiki are never updated.
"""
import argparse
import json
import os
import re
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from pymongo import MongoClient


def norm(value):
    value = unicodedata.normalize("NFKD", str(value or "")).casefold()
    value = "".join(c for c in value if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^a-z0-9]+", " ", value).split())


def make_client(uri):
    parsed = urlparse(uri)
    options = parse_qs(parsed.query)
    tls = parsed.scheme == "mongodb+srv" or any(
        value.lower() in {"true", "1", "yes"}
        for key in ("tls", "ssl") for value in options.get(key, [])
    )
    if tls:
        import certifi
        return MongoClient(uri, tlsCAFile=certifi.where(), serverSelectionTimeoutMS=10000)
    return MongoClient(uri, serverSelectionTimeoutMS=10000)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Reviewed JSON from export_local_cinema_candidates.py")
    parser.add_argument("--uri", default=os.getenv("CINESCRAPPER_MONGO_URI", os.getenv("MONGODB_URI", "mongodb://localhost:27017")))
    parser.add_argument("--database", default=os.getenv("CINESCRAPPER_MONGODB_DATABASE", os.getenv("MONGODB_DATABASE", "cinescrapper")))
    parser.add_argument("--collection", default=os.getenv("CINESCRAPPER_MONGODB_COLLECTION", os.getenv("MONGODB_COLLECTION", "cinemas")))
    parser.add_argument("--apply", action="store_true", help="Insert approved entries; default is dry-run.")
    args = parser.parse_args()

    data = json.loads(Path(args.input).expanduser().read_text(encoding="utf-8"))
    entries = data if isinstance(data, list) else data.get("missing", [])
    if not isinstance(entries, list):
        raise ValueError("Input must be a list or contain a missing list.")

    client = make_client(args.uri)
    try:
        client.admin.command("ping")
        collection = client[args.database][args.collection]
        print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
        inserted = skipped = rejected = 0
        for entry in entries:
            if entry.get("status") != "approved":
                rejected += 1
                continue
            title = str(entry.get("title") or entry.get("film_title") or "").strip()
            try:
                year = int(entry.get("year"))
            except (TypeError, ValueError):
                print(f"[SKIP] Invalid year for {title!r}")
                skipped += 1
                continue
            if not title:
                skipped += 1
                continue

            existing = list(collection.find({"year": year}, {"title": 1}).limit(1000))
            if any(norm(doc.get("title")) == norm(title) for doc in existing):
                print(f"[SKIP DUPLICATE] {title} ({year})")
                skipped += 1
                continue

            tracks = []
            for track in entry.get("tracks", []):
                filename = str(track.get("fileName") or track.get("filename") or "").strip()
                relative_path = str(track.get("relative_path") or "").strip()
                if filename and relative_path:
                    tracks.append({
                        "fileName": filename,
                        "relative_path": relative_path,
                        "add_collection": bool(track.get("add_collection", False)),
                    })

            document = {
                "title": title,
                "year": year,
                "downloaded": False,
                "add_collection": False,
                "soundtrack": {"tracks": tracks},
            }
            if args.apply:
                collection.insert_one(document)
                print(f"[INSERTED] {title} ({year}) - {len(tracks)} tracks")
                inserted += 1
            else:
                print(f"[DRY RUN] Would insert {title} ({year}) - {len(tracks)} tracks")
                inserted += 1

        print(f"Approved entries inserted/would insert: {inserted}")
        print(f"Skipped duplicates/invalid entries: {skipped}")
        print(f"Not approved: {rejected}")
        if not args.apply:
            print("Dry run only. Use --apply after reviewing the output.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
