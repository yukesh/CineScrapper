#!/usr/bin/env python3
"""Safely rename legacy MongoDB soundtrack fields to soundtrack_wiki.

Dry-run is the default. Existing soundtrack_wiki values are never overwritten.
Documents containing both fields are reported for manual review.
"""
import argparse
import os
from urllib.parse import parse_qs, urlparse

from pymongo import MongoClient


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
    parser.add_argument("--uri", default=os.getenv("CINESCRAPPER_MONGO_URI", os.getenv("MONGODB_URI", "mongodb://localhost:27017")))
    parser.add_argument("--database", default=os.getenv("CINESCRAPPER_MONGODB_DATABASE", os.getenv("MONGODB_DATABASE", "cinescrapper")))
    parser.add_argument("--collection", default=os.getenv("CINESCRAPPER_MONGODB_COLLECTION", os.getenv("MONGODB_COLLECTION", "cinemas")))
    parser.add_argument("--apply", action="store_true", help="Apply the field rename; otherwise dry-run.")
    args = parser.parse_args()

    client = make_client(args.uri)
    try:
        client.admin.command("ping")
        collection = client[args.database][args.collection]
        legacy = list(collection.find({"soundtrack": {"$exists": True}}, {"title": 1, "year": 1, "soundtrack_wiki": 1}))
        to_rename = [doc for doc in legacy if "soundtrack_wiki" not in doc]
        conflicts = [doc for doc in legacy if "soundtrack_wiki" in doc]
        print(f"Database: {args.database}.{args.collection}")
        print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
        print(f"Legacy soundtrack fields found: {len(legacy)}")
        print(f"Safe to rename: {len(to_rename)}")
        print(f"Both soundtrack and soundtrack_wiki (left untouched): {len(conflicts)}")
        for doc in conflicts:
            print(f"[CONFLICT] {doc.get('title', '<untitled>')} ({doc.get('year', '?')}) _id={doc['_id']}")
        if args.apply:
            changed = 0
            for doc in to_rename:
                result = collection.update_one(
                    {"_id": doc["_id"], "soundtrack_wiki": {"$exists": False}, "soundtrack": {"$exists": True}},
                    {"$rename": {"soundtrack": "soundtrack_wiki"}},
                )
                changed += result.modified_count
            print(f"Renamed {changed} document(s).")
        else:
            print("Dry run only; MongoDB was not modified. Add --apply to rename safe documents.")
    finally:
        client.close()


if __name__ == "__main__":
    main()
