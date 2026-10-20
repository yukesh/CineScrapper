
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
        """Backward-compatible upsert API."""
        return self._collection.update_one(
            self._upsert_filter(cinema),
            {"$set": cinema.to_dict()},
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
