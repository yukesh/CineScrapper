
#!/usr/bin/env python3
"""Scan a language library and write an OST-only JSON manifest.

Direct audio files inside a cinema folder and audio files inside its
Original Soundtrack subfolder are combined into one OST entry.

Background Score and other subfolders are excluded from the manifest.
This script never modifies MongoDB.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

AUDIO_EXTENSIONS = {
    ".m4a",
    ".flac",
    ".alac",
    ".mp3",
    ".aac",
    ".wav",
    ".aiff",
    ".ogg",
    ".opus",
}

FILM_RE = re.compile(r"^(?P<title>.+?)\s*\[(?P<year>\d{4})\]\s*$")
OST_NAME = "Original Soundtrack"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


def is_audio(path: Path) -> bool:
    """Return True if path is a supported audio file."""
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


def is_ost_folder(name: str) -> bool:
    """Recognise common names for the Original Soundtrack folder."""
    normalized = re.sub(r"[\W_]+", " ", name.casefold()).strip()

    return normalized in {
        "original soundtrack",
        "original soundtracks",
        "ost",
    }


def list_audio_files(directory: Path) -> list[Path]:
    """List direct audio files, logging errors instead of hiding them."""
    try:
        children = list(directory.iterdir())
    except OSError:
        logger.exception("Unable to read directory: %s", directory)
        return []

    files = []

    for path in children:
        try:
            if is_audio(path):
                files.append(path)
        except OSError:
            logger.exception("Unable to inspect file: %s", path)

    return sorted(files, key=lambda path: path.name.casefold())


def list_audio_files_recursive(directory: Path) -> list[Path]:
    """List audio files recursively, logging unreadable directories."""
    found: list[Path] = []

    def on_walk_error(exc: OSError) -> None:
        logger.warning(
            "Unable to scan directory: %s",
            exc,
        )

    for current, _dirnames, filenames in os.walk(
            directory,
            onerror=on_walk_error,
    ):
        current_path = Path(current)

        for filename in filenames:
            path = current_path / filename

            if path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue

            try:
                if path.is_file():
                    found.append(path)
            except OSError:
                logger.exception("Unable to inspect audio file: %s", path)

    return sorted(
        found,
        key=lambda path: path.as_posix().casefold(),
    )


def scan(
        base_path: Path,
        language_code: str,
        language_folder: str | None = None,
) -> dict:
    """Scan cinema folders and return an OST-only manifest."""
    root = base_path.expanduser().resolve()

    if not root.is_dir():
        logger.error("Base path is not a directory: %s", root)
        raise ValueError(f"Base path is not a directory: {root}")

    folder_name = language_folder or root.name
    items: list[dict] = []
    directories: list[Path] = []

    def on_walk_error(exc: OSError) -> None:
        logger.warning("Unable to scan directory: %s", exc)

    for current, dirnames, _filenames in os.walk(
            root,
            onerror=on_walk_error,
    ):
        current_path = Path(current)

        # Sort traversal for repeatable output.
        dirnames.sort(key=str.casefold)

        for dirname in dirnames:
            directories.append(current_path / dirname)

    film_dirs = sorted(
        (
            directory
            for directory in directories
            if FILM_RE.match(directory.name)
        ),
        key=lambda path: path.as_posix().casefold(),
    )

    if not film_dirs:
        logger.warning(
            "No cinema folders matching 'Title [YYYY]' found under %s",
            root,
        )

    recognised_film_dirs = set(film_dirs)

    # Report audio-containing directories that aren't inside a recognised
    # cinema folder. These files cannot be assigned to a cinema reliably.
    for directory in directories:
        if any(parent in recognised_film_dirs for parent in directory.parents):
            continue

        if FILM_RE.match(directory.name):
            continue

        if list_audio_files(directory):
            logger.warning(
                "Audio files found outside a recognised cinema folder: %s",
                directory.relative_to(root).as_posix(),
            )

    for film_dir in film_dirs:
        match = FILM_RE.match(film_dir.name)
        assert match is not None

        # Direct audio files in the cinema folder are OST tracks.
        tracks = list_audio_files(film_dir)

        try:
            children = sorted(
                (
                    child
                    for child in film_dir.iterdir()
                    if child.is_dir()
                ),
                key=lambda child: child.name.casefold(),
            )
        except OSError:
            logger.exception(
                "Unable to list subfolders for cinema: %s",
                film_dir,
            )
            children = []

        # Combine explicit Original Soundtrack folders with direct tracks.
        for child in children:
            if is_ost_folder(child.name):
                tracks.extend(list_audio_files_recursive(child))
                continue

            # Background Score and other named folders aren't included.
            # Log when audio is intentionally excluded for visibility.
            excluded_audio = list_audio_files_recursive(child)

            if excluded_audio:
                if re.sub(
                        r"[\W_]+", " ", child.name.casefold()
                ).strip() in {
                    "background score",
                    "background scores",
                    "bgm",
                }:
                    logger.info(
                        "Ignoring Background Score folder: %s (%d audio files)",
                        child.relative_to(root).as_posix(),
                        len(excluded_audio),
                    )
                else:
                    logger.warning(
                        "Ignoring audio in non-OST folder: %s (%d audio files)",
                        child.relative_to(root).as_posix(),
                        len(excluded_audio),
                    )

        # Deduplicate paths and produce stable ordering.
        tracks = sorted(
            set(tracks),
            key=lambda path: path.as_posix().casefold(),
        )

        if not tracks:
            logger.warning(
                "No OST audio files found for cinema folder: %s",
                film_dir.relative_to(root).as_posix(),
            )
            continue

        relative_film_path = film_dir.relative_to(root).as_posix()

        item = {
            "film_title": match.group("title").strip(),
            "year": int(match.group("year")),
            "soundtrack_folder_name": OST_NAME,
            "language": language_code,
            "language_folder": folder_name,
            "relative_path": relative_film_path,
            "tracks": [
                {
                    "filename": path.name,
                    "relative_path": path.relative_to(root).as_posix(),
                }
                for path in tracks
            ],
        }

        items.append(item)

        logger.info(
            "Scanned OST: %s [%s] - %d tracks",
            item["film_title"],
            item["year"],
            len(tracks),
        )

    logger.info(
        "Scan complete: %d OST entries found under %s",
        len(items),
        root,
    )

    return {
        "schema_version": 2,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "base_path_is_not_stored": True,
        "language": language_code,
        "language_folder": folder_name,
        "items": items,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--base-path",
        required=True,
        help="Language root, e.g. .../ALAC/Thamizh",
    )
    parser.add_argument(
        "--language-code",
        required=True,
        help="ISO 639-1 code, e.g. ta, hi, kn, ml, te",
    )
    parser.add_argument(
        "--language-folder",
        help="Folder name to store; defaults to the base path folder name",
    )
    parser.add_argument(
        "--output",
        default="library-scan.json",
        help="Output JSON manifest path",
    )

    args = parser.parse_args()

    try:
        manifest = scan(
            Path(args.base_path),
            args.language_code,
            args.language_folder,
        )

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    except (OSError, ValueError) as exc:
        logger.error("Library scan failed: %s", exc)
        return 1

    logger.info(
        "Manifest written to %s (%d OST entries)",
        output_path,
        len(manifest["items"]),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
