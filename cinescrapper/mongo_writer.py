
"""Write cinema documents to MongoDB using upserts."""

import re
from typing import Optional
from urllib.parse import parse_qs, urlparse

from cinescrapper.cine_model import CineInfo
from cinescrapper.logger import get_logger

logger = get_logger()


def _normalized_title(title) -> str:
    """Normalize a title for matching only; do not use it as a stored title."""
    if not isinstance(title, str):
        return ""
    return re.sub(r"\s+", " ", title.replace(":", " ")).strip().casefold()


class MongoCinemaWriter:
    """Writes cinema documents to MongoDB using an upsert."""

    def __init__(
            self,
            connection_string: str,
            database_name: str,
            collection_name: str,
            collection=None,
    ):
        self._client = None

        if collection is not None:
            self._collection = collection
        else:
            self._client = self._create_client(connection_string)
            self._collection = self._client[database_name][collection_name]

    @staticmethod
    def _create_client(connection_string: str):
        try:
            from pymongo import MongoClient
        except ImportError as exception:
            raise RuntimeError("MongoDB support requires pymongo.") from exception

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
            except ImportError as exception:
                raise RuntimeError(
                    "TLS MongoDB connections require certifi for CA certificates."
                ) from exception

            return MongoClient(
                connection_string,
                tlsCAFile=certifi.where(),
            )

        return MongoClient(connection_string)

    @staticmethod
    def _upsert_filter(cinema: CineInfo):
        if cinema.ref:
            return {"ref": cinema.ref}
        return {"title": cinema.title, "year": cinema.year}

    def _find_existing_title_match(self, cinema: CineInfo):
        """
        Find a legacy title variant for the same year.

        Used only when the cinema has no ref and an exact title/year match
        was not found. Returns a match only when the normalized title is
        unique for that year.
        """
        if cinema.ref or cinema.year is None:
            return None

        find_method = getattr(self._collection, "find", None)
        if not callable(find_method):
            return None

        expected = _normalized_title(cinema.title)
        if not expected:
            return None

        matches = [
            document
            for document in find_method({"year": cinema.year})
            if _normalized_title(document.get("title")) == expected
        ]

        if len(matches) == 1:
            return matches[0]

        if len(matches) > 1:
            logger.warning(
                "Multiple title variants match %s (%s); skipping fallback match",
                cinema.title,
                cinema.year,
            )

        return None

    @staticmethod
    def _preserve_existing_flags(document: dict, existing: dict) -> dict:
        """Preserve user-managed flags when metadata is refreshed by a scrape."""
        # These are user-managed/persistent flags. A normal Wikipedia scrape
        # should never reset them to dataclass defaults. Preserve all existing
        # values when refreshing metadata; dedicated tools can change them.
        for flag in ("downloaded", "add_collection"):
            if flag in existing:
                document[flag] = existing[flag]

        existing_soundtrack = existing.get("soundtrack_wiki")
        incoming_soundtrack = document.get("soundtrack_wiki")
        # A scrape that did not retrieve soundtrack metadata must not erase
        # previously stored Wikipedia metadata.
        if incoming_soundtrack is None and isinstance(existing_soundtrack, dict):
            document["soundtrack_wiki"] = existing_soundtrack
            incoming_soundtrack = existing_soundtrack
        if isinstance(existing_soundtrack, dict) and isinstance(incoming_soundtrack, dict):
            if "add_collection" in existing_soundtrack:
                incoming_soundtrack["add_collection"] = existing_soundtrack["add_collection"]

            existing_tracks = existing_soundtrack.get("tracks", [])
            incoming_tracks = incoming_soundtrack.get("tracks", [])
            if isinstance(existing_tracks, list) and isinstance(incoming_tracks, list):
                # Match by stable track number/title where possible. Preserve a
                # track's selection flag even if other metadata is refreshed.
                def track_key(track):
                    if not isinstance(track, dict):
                        return None
                    number = track.get("number")
                    title = _normalized_title(track.get("title"))
                    if number is not None and title:
                        return (str(number), title)
                    if title:
                        return (None, title)
                    return None

                flags_by_key = {}
                for old_track in existing_tracks:
                    key = track_key(old_track)
                    if key is not None and isinstance(old_track, dict) and "add_collection" in old_track:
                        flags_by_key.setdefault(key, []).append(old_track["add_collection"])

                for new_track in incoming_tracks:
                    key = track_key(new_track)
                    if key is not None and key in flags_by_key and flags_by_key[key]:
                        new_track["add_collection"] = flags_by_key[key].pop(0)
                    elif key is not None:
                        new_track.setdefault("add_collection", False)
                    elif isinstance(new_track, dict):
                        new_track.setdefault("add_collection", False)

        return document

    def save_cinema(self, cinema: CineInfo) -> str:
        """
        Insert a new movie, update changed fields, or skip an identical document.

        Returns: ``inserted``, ``updated`` or ``unchanged``.
        """
        document = cinema.to_dict()
        query = self._upsert_filter(cinema)
        existing = self._collection.find_one(query)

        if existing is None:
            existing = self._find_existing_title_match(cinema)

            if existing is not None:
                # Use the existing document's identity for the update.
                if cinema.ref:
                    query = {"ref": cinema.ref}
                elif "_id" in existing:
                    query = {"_id": existing["_id"]}
                else:
                    query = {
                        "title": existing.get("title"),
                        "year": existing.get("year"),
                    }

        if existing is None:
            result = self._collection.update_one(
                query,
                {"$set": document},
                upsert=True,
            )
            logger.info("Inserted movie %s (%s)", cinema.title, cinema.year)
            logger.debug(
                "MongoDB insert/upsert result: %s",
                getattr(result, "raw_result", result),
            )
            return "inserted"

        document = self._preserve_existing_flags(document, existing)

        # If this is the same logical title, keep its existing stored title.
        # This prevents routine scraping from renaming legacy records.
        existing_title = existing.get("title")
        if (
                existing_title
                and _normalized_title(existing_title)
                == _normalized_title(document.get("title"))
        ):
            document["title"] = existing_title

        unchanged = all(
            key in existing and existing[key] == value
            for key, value in document.items()
        )

        if unchanged:
            logger.debug(
                "No changes for %s (%s); skipping MongoDB write",
                cinema.title,
                cinema.year,
            )
            return "unchanged"

        result = self._collection.update_one(
            query,
            {"$set": document},
            upsert=False,
        )
        logger.info(
            "Updated changed fields for %s (%s)",
            cinema.title,
            cinema.year,
        )
        logger.debug(
            "MongoDB update result: %s",
            getattr(result, "raw_result", result),
        )
        return "updated"

    def upsert_cinema(self, cinema: CineInfo):
        """Backward-compatible upsert API that preserves existing flags."""
        document = cinema.to_dict()
        query = self._upsert_filter(cinema)
        existing = self._collection.find_one(query)
        if existing is not None:
            document = self._preserve_existing_flags(document, existing)
        return self._collection.update_one(
            query,
            {"$set": document},
            upsert=True,
        )

    def close(self):
        if self._client is not None:
            self._client.close()


def create_mongo_writer(
        enabled: bool,
        connection_string: str,
        database_name: str,
        collection_name: str,
) -> Optional[MongoCinemaWriter]:
    if not enabled:
        return None

    return MongoCinemaWriter(
        connection_string,
        database_name,
        collection_name,
    )
