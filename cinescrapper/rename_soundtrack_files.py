#!/usr/bin/env python3
"""
Safely normalise soundtrack folder and file names.

Rules:
1. Remove leading numeric prefixes from filenames, e.g.:
   "1 - 01 - Song.m4a" -> "Song.m4a"
   "03. Song.lrc"       -> "Song.lrc"
2. Remove hyphens at the beginning and end of the filename stem.
3. Remove "(Original Motion Picture Soundtrack)" from folder names.
4. If a folder's immediate parent is named exactly YYYY, append " [YYYY]"
   to that folder name unless that year suffix is already present.

Default mode is DRY RUN. Nothing is renamed unless --apply is supplied.
The script processes all file types, including .m4a and .lrc, but does not
change file contents or audio data.
"""

from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

LOG = logging.getLogger("soundtrack_rename")

YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
YEAR_SUFFIX_RE = re.compile(r"\[((?:19|20)\d{2})\]")
OST_FOLDER_RE = re.compile(
    r"\s*\(\s*Original\s+Motion\s+Picture\s+Soundtrack\s*\)\s*",
    re.IGNORECASE,
)

# A numeric prefix can be a simple number ("01 "), or a numbered segment
# such as "1 - 01 - ". Repeat to handle "1 - 01 - 02 - Song".
LEADING_NUMBER_SEGMENT_RE = re.compile(
    r"^\s*\d+\s*(?:(?:[-–—.]|[)])\s*|\s+)"
)



def clean_file_name(path: Path) -> str:
    """Return a cleaned filename, preserving and normalising its extension."""
    name = path.name
    suffix = path.suffix
    stem = name[:-len(suffix)] if suffix else name

    # If a known extension is missing its dot or has whitespace before it,
    # recognise it and restore the proper extension.
    known_extensions = (".m4a", ".lrc", ".flac", ".mp3", ".wav", ".aac",
                        ".alac", ".ogg", ".opus", ".aiff", ".wma")

    if not suffix or suffix.lower() not in known_extensions:
        match = re.search(
            r"\s*\.?\s*(m4a|lrc|flac|mp3|wav|aac|alac|ogg|opus|aiff|wma)$",
            name,
            re.IGNORECASE,
        )
        if match:
            suffix = "." + match.group(1)
            stem = name[:match.start()]

    # Repeatedly remove leading numeric prefixes.
    previous = None
    while stem != previous:
        previous = stem
        stem = LEADING_NUMBER_SEGMENT_RE.sub("", stem, count=1)

    # Remove hyphens/dashes at the edges of the stem.
    stem = re.sub(r"^\s*[-–—]+\s*", "", stem)
    stem = re.sub(r"\s*[-–—]+\s*$", "", stem)

    # Remove whitespace around the stem and before the extension.
    # Collapse multiple consecutive whitespace characters into one space.
    stem = re.sub(r"\s+", " ", stem).strip()

    if not stem:
        LOG.warning("Skipping name that would become empty: %s", path)
        return path.name

    return f"{stem}{suffix}"



def clean_folder_name(path: Path) -> str:
    """Clean folder names and place [YYYY] before audio format labels."""
    name = OST_FOLDER_RE.sub(" ", path.name)
    name = re.sub(r"\s*[-–—]+\s*$", "", name)
    name = re.sub(r"^\s*[-–—]+\s*", "", name)
    name = re.sub(r"\s+", " ", name).strip()

    parent_name = path.parent.name
    parent_year = parent_name if YEAR_RE.fullmatch(parent_name) else None

    # Recognise a year already present anywhere in the folder name.
    year_match = YEAR_SUFFIX_RE.search(name)
    year = year_match.group(1) if year_match else parent_year

    # Remove the existing year temporarily so it can be positioned correctly.
    if year_match:
        name = (
                name[:year_match.start()] + name[year_match.end():]
        ).strip()
        name = re.sub(r"\s+", " ", name).strip()

    if year:
        # Place the year before audio format labels such as:
        # "16Bit ALAC", "24Bit FLAC", "ALAC", or "FLAC".
        format_pattern = re.compile(
            r"\s+((?:\d+\s*Bit\s+)?(?:ALAC|FLAC))$",
            re.IGNORECASE,
        )
        match = format_pattern.search(name)

        if match:
            title = name[:match.start()].strip()
            audio_format = match.group(1).strip()
            name = f"{title} [{year}] {audio_format}"
        else:
            name = f"{name} [{year}]".strip()

    if not name:
        LOG.warning("Skipping folder that would become empty: %s", path)
        return path.name

    return name


def plan_renames(root: Path) -> list[tuple[Path, Path]]:
    """Build a deterministic rename plan without changing the filesystem."""
    planned: list[tuple[Path, Path]] = []

    # Files first in the plan; folders are later sorted deepest-first.
    for path in sorted((p for p in root.rglob("*") if p.is_file())):
        new_name = clean_file_name(path)
        if new_name != path.name:
            planned.append((path, path.with_name(new_name)))

    folders = sorted(
        (p for p in root.rglob("*") if p.is_dir()),
        key=lambda p: (len(p.parts), str(p)),
        reverse=True,
    )
    for path in folders:
        new_name = clean_folder_name(path)
        if new_name != path.name:
            planned.append((path, path.with_name(new_name)))

    return planned


def validate_plan(renames: list[tuple[Path, Path]]) -> list[tuple[Path, Path]]:
    """Drop unsafe renames that collide with existing or planned destinations."""
    source_paths = {src.resolve() for src, _ in renames}
    destination_map: dict[Path, Path] = {}
    safe: list[tuple[Path, Path]] = []

    for src, dst in renames:
        resolved_dst = dst.resolve()
        if resolved_dst in destination_map:
            LOG.error(
                "Name collision: both %s and %s would become %s; skipping %s",
                destination_map[resolved_dst], src, dst, src,
            )
            continue

        if dst.exists() and dst.resolve() not in source_paths:
            LOG.error("Destination already exists; skipping rename: %s -> %s", src, dst)
            continue

        destination_map[resolved_dst] = src
        safe.append((src, dst))

    return safe


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean soundtrack filenames and movie folder names safely."
    )
    parser.add_argument(
        "root",
        type=Path,
        help="Root music folder to process (for example, /path/to/ALAC/Thamizh)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform renames. Without this flag, runs in dry-run mode.",
    )
    args = parser.parse_args()

    root = args.root.expanduser()
    if not root.exists() or not root.is_dir():
        LOG.error("Root folder does not exist or is not a directory: %s", root)
        return 2

    root = root.resolve()
    renames = validate_plan(plan_renames(root))

    # Process deepest paths first so child paths are renamed before parents.
    renames.sort(
        key=lambda pair: (len(pair[0].parts), pair[0].is_dir()),
        reverse=True,
    )

    mode = "APPLY" if args.apply else "DRY RUN"
    files_planned = sum(1 for src, _ in renames if src.is_file())
    folders_planned = sum(1 for src, _ in renames if src.is_dir())

    LOG.info("%s: %d rename(s) planned.", mode, len(renames))
    LOG.info("Root folder: %s", root)

    files_renamed = 0
    folders_renamed = 0
    skipped = 0
    failed = 0

    for src, dst in renames:
        if not src.exists():
            LOG.warning(
                "Source no longer exists; skipping: %s",
                src,
            )
            skipped += 1
            continue

        if dst.exists():
            LOG.error("Destination already exists; skipping: %s -> %s", src, dst)
            skipped += 1
            continue

        is_file = src.is_file()
        LOG.info("%s -> %s", src, dst)

        if not args.apply:
            continue

        try:
            src.rename(dst)
            if is_file:
                files_renamed += 1
            else:
                folders_renamed += 1
        except OSError as exc:
            LOG.error("Failed to rename %s: %s", src, exc)
            failed += 1

    print()
    print("=" * 50)
    print(f"SUMMARY ({mode})")
    print("=" * 50)
    print(f"Root folder          : {root}")

    if args.apply:
        print(f"Files renamed        : {files_renamed}")
        print(f"Folders renamed      : {folders_renamed}")
        print(f"Total renamed        : {files_renamed + folders_renamed}")
    else:
        print(f"Files to be renamed  : {files_planned}")
        print(f"Folders to be renamed: {folders_planned}")
        print(f"Total planned        : {len(renames)}")

    print(f"Skipped              : {skipped}")
    print(f"Failed               : {failed}")

    if not args.apply:
        print("\nDry run only. No files or folders were changed.")
        print("Run again with --apply to perform the renames.")
    else:
        print("\nRename pass complete. Review WARNING/ERROR messages above.")

    print("=" * 50)
    return 1 if failed else 0


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    sys.exit(main())
