"""Copy tracks marked for collection from a local library into a curated folder.

The command reads ``soundtrack.tracks`` from MongoDB and copies only entries
with ``add_collection: true``. It defaults to a dry run; use ``--apply`` to
copy audio and matching same-stem LRC files.
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlparse

from cinescrapper.env import add_mongo_uri_profile_argument, resolve_mongo_settings


def make_client(uri: str):
    from pymongo import MongoClient

    parsed = urlparse(uri)
    options = parse_qs(parsed.query)
    tls = parsed.scheme == "mongodb+srv" or any(
        value.lower() in {"true", "1", "yes"}
        for key in ("tls", "ssl")
        for value in options.get(key, [])
    )
    client_options = {"serverSelectionTimeoutMS": 10000}
    if tls:
        import certifi
        client_options["tlsCAFile"] = certifi.where()
    return MongoClient(uri, **client_options)


def safe_component(value: object) -> str:
    """Make a title safe as one directory component."""
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(value or "")).strip(" .")
    return text or "Untitled"


def selected_tracks(documents: list[dict]) -> list[dict]:
    """Flatten selected tracks while keeping their cinema metadata."""
    rows = []
    for cinema in documents:
        soundtrack = cinema.get("soundtrack")
        tracks = soundtrack.get("tracks", []) if isinstance(soundtrack, dict) else []
        if not isinstance(tracks, list):
            continue
        selected = [track for track in tracks if isinstance(track, dict) and track.get("add_collection") is True]
        year = cinema.get("year")
        title = cinema.get("title") or "Untitled"
        for track in selected:
            relative = str(track.get("relative_path") or "").strip()
            filename = str(track.get("fileName") or "").strip()
            if not relative:
                relative = filename
            path = PurePosixPath(relative.replace("\\", "/"))
            if not relative or path.is_absolute() or ".." in path.parts:
                raise ValueError(f"Unsafe or missing track relative_path for {title!r}: {relative!r}")
            rows.append({
                "year": str(year or "Unknown Year"),
                "title": str(title),
                "relative_path": path,
                "filename": path.name,
                "album_track_count": len(selected),
            })
    return rows


def copy_plan(rows: list[dict], source_root: Path, target_root: Path) -> list[tuple[Path, Path]]:
    """Resolve source and destination paths, rejecting source-root escapes."""
    plan = []
    for row in rows:
        source = (source_root / Path(*row["relative_path"].parts)).resolve()
        if not source.is_relative_to(source_root):
            raise ValueError(f"Track path escapes source root: {row['relative_path']}")
        if row["album_track_count"] == 1:
            destination_dir = target_root / safe_component(row["year"])
        else:
            cinema_dir = f"{safe_component(row['title'])} [{safe_component(row['year'])}]"
            destination_dir = target_root / safe_component(row["year"]) / cinema_dir
        destination = destination_dir / row["filename"]
        if not source.is_file():
            raise FileNotFoundError(f"Source track not found: {source}")
        plan.append((source, destination))
        lrc = source.with_suffix(".lrc")
        if lrc.is_file():
            plan.append((lrc, destination.with_suffix(".lrc")))
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True, help="Root that contains track relative_path values")
    parser.add_argument("--target-folder", type=Path, required=True, help="Destination root for copied tracks")
    parser.add_argument("--uri", help="Override the MongoDB URI")
    parser.add_argument("--database", help="Override the MongoDB database")
    parser.add_argument("--collection", help="Override the MongoDB collection")
    parser.add_argument("--apply", action="store_true", help="Perform the copy; otherwise show the plan only")
    add_mongo_uri_profile_argument(parser)
    args = parser.parse_args()

    try:
        settings = resolve_mongo_settings(
            uri=args.uri,
            database=args.database,
            collection=args.collection,
            profile=args.mongo_uri_profile,
        )
        source_root = args.source_root.expanduser().resolve()
        if not source_root.is_dir():
            raise ValueError(f"Source root is not a directory: {source_root}")
        target_root = args.target_folder.expanduser().resolve()

        client = make_client(settings["uri"])
        try:
            client.admin.command("ping")
            collection = client[settings["database"]][settings["collection"]]
            documents = list(collection.find(
                {"soundtrack.tracks.add_collection": True},
                {"title": 1, "year": 1, "soundtrack.tracks": 1},
            ))
        finally:
            client.close()

        rows = selected_tracks(documents)
        plan = copy_plan(rows, source_root, target_root)
        destinations = set()
        for source, destination in plan:
            if destination in destinations:
                raise FileExistsError(f"Multiple selected tracks resolve to the same destination: {destination}")
            destinations.add(destination)
            if destination.exists() and not (destination.is_file() and source.samefile(destination)):
                raise FileExistsError(f"Refusing to overwrite existing file: {destination}")
        print(f"MongoDB source: {settings['database']}.{settings['collection']}")
        print(f"Selected tracks: {len(rows)}; files including LRC: {len(plan)}")
        print(f"Mode: {'APPLY' if args.apply else 'DRY RUN'}")
        for source, destination in plan:
            print(f"{source} -> {destination}")
        if not args.apply:
            print("Dry run only. Add --apply to copy these files.")
            return 0

        copied = 0
        for source, destination in plan:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                print(f"[SAME FILE] {destination}")
                continue
            shutil.copy2(source, destination)
            copied += 1
        print(f"Copied {copied} file(s).")
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        parser.exit(1, f"Error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
