#!/usr/bin/env python3
"""Find local-library cinema folders not represented by title/year in MongoDB.

The output is a review file, not an automatic insert. Set status to "approved"
only after checking possible multilingual/title variants.
"""
import argparse
import difflib
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
    parser.add_argument("--manifest", required=True, help="JSON output from scan_library.py")
    parser.add_argument("--uri", default=os.getenv("CINESCRAPPER_MONGO_URI", os.getenv("MONGODB_URI", "mongodb://localhost:27017")))
    parser.add_argument("--database", default=os.getenv("CINESCRAPPER_MONGODB_DATABASE", os.getenv("MONGODB_DATABASE", "cinescrapper")))
    parser.add_argument("--collection", default=os.getenv("CINESCRAPPER_MONGODB_COLLECTION", os.getenv("MONGODB_COLLECTION", "cinemas")))
    parser.add_argument("--output", default="reports/local_cinemas_for_review.json")
    parser.add_argument("--threshold", type=float, default=0.55, help="Minimum similarity score for suggestions, 0-1.")
    args = parser.parse_args()

    data = json.loads(Path(args.manifest).expanduser().read_text(encoding="utf-8"))
    entries = data if isinstance(data, list) else data.get("items", [])
    if not isinstance(entries, list):
        raise ValueError("Manifest must be a list or contain an items list.")

    client = make_client(args.uri)
    try:
        client.admin.command("ping")
        collection = client[args.database][args.collection]
        catalogue = list(collection.find({}, {"title": 1, "year": 1}))
        missing = []
        exact_count = 0

        for entry in entries:
            title = str(entry.get("film_title") or entry.get("title") or "").strip()
            try:
                year = int(entry.get("year"))
            except (TypeError, ValueError):
                print(f"[SKIP] Invalid year/title in manifest entry: {entry!r}")
                continue
            if not title:
                continue

            same_year = []
            for document in catalogue:
                try:
                    candidate_year = int(document.get("year"))
                except (TypeError, ValueError):
                    continue
                if candidate_year == year:
                    same_year.append(document)
            if any(norm(d.get("title")) == norm(title) for d in same_year):
                exact_count += 1
                continue

            candidates = []
            for doc in catalogue:
                candidate_title = str(doc.get("title") or "")
                score = difflib.SequenceMatcher(None, norm(title), norm(candidate_title)).ratio()
                if score >= args.threshold:
                    candidates.append({
                        "title": candidate_title,
                        "year": doc.get("year"),
                        "score": round(score, 3),
                        "same_year": doc.get("year") == year,
                    })
            candidates.sort(key=lambda x: (x["same_year"], x["score"]), reverse=True)

            tracks = []
            for track in entry.get("tracks", []):
                filename = str(track.get("filename") or track.get("fileName") or "").strip()
                relative_path = str(track.get("relative_path") or "").strip()
                if filename and relative_path:
                    tracks.append({
                        "fileName": filename,
                        "relative_path": relative_path,
                        "add_collection": False,
                    })

            missing.append({
                "title": title,
                "year": year,
                "language": entry.get("language"),
                "language_folder": entry.get("language_folder"),
                "relative_path": entry.get("relative_path"),
                "tracks": tracks,
                "possible_matches": candidates[:5],
                "status": "review",
            })

        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({
            "schema_version": 1,
            "source_manifest": str(Path(args.manifest).expanduser()),
            "exact_matches_skipped": exact_count,
            "missing": missing,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Exact title/year matches skipped: {exact_count}")
        print(f"Local cinemas needing review: {len(missing)}")
        print(f"Review report: {output.resolve()}")
        print('Set "status": "approved" only for genuinely distinct missing cinemas.')
    finally:
        client.close()


if __name__ == "__main__":
    main()
