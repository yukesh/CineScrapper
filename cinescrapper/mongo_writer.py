from typing import Optional
from urllib.parse import parse_qs, urlparse

from cinescrapper.cine_model import CineInfo
from cinescrapper.logger import get_logger

logger = get_logger()


class MongoCinemaWriter:
    """Writes cinema documents to MongoDB using an upsert."""

    def __init__(self, connection_string: str, database_name: str, collection_name: str, collection=None):
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
                raise RuntimeError("TLS MongoDB connections require certifi for CA certificates.") from exception
            return MongoClient(connection_string, tlsCAFile=certifi.where())
        return MongoClient(connection_string)

    @staticmethod
    def _upsert_filter(cinema: CineInfo):
        if cinema.ref:
            return {"ref": cinema.ref}
        return {"title": cinema.title, "year": cinema.year}

    def save_cinema(self, cinema: CineInfo) -> str:
        """Insert a new movie, update changed fields, or skip an identical document.

        Returns one of: ``inserted``, ``updated`` or ``unchanged``.
        Only fields emitted by ``CineInfo.to_dict()`` are compared; MongoDB's
        internal ``_id`` and unrelated metadata do not trigger an update.
        """
        document = cinema.to_dict()
        query = self._upsert_filter(cinema)
        existing = self._collection.find_one(query)

        if existing is None:
            result = self._collection.update_one(query, {"$set": document}, upsert=True)
            logger.info("Inserted movie %s (%s)", cinema.title, cinema.year)
            logger.debug("MongoDB insert/upsert result: %s", getattr(result, "raw_result", result))
            return "inserted"

        unchanged = all(key in existing and existing[key] == value for key, value in document.items())
        if unchanged:
            logger.debug("No changes for %s (%s); skipping MongoDB write", cinema.title, cinema.year)
            return "unchanged"

        result = self._collection.update_one(query, {"$set": document}, upsert=False)
        logger.info("Updated changed fields for %s (%s)", cinema.title, cinema.year)
        logger.debug("MongoDB update result: %s", getattr(result, "raw_result", result))
        return "updated"

    def upsert_cinema(self, cinema: CineInfo):
        """Backward-compatible upsert API."""
        return self._collection.update_one(
            self._upsert_filter(cinema), {"$set": cinema.to_dict()}, upsert=True
        )

    def close(self):
        if self._client is not None:
            self._client.close()


def create_mongo_writer(enabled: bool, connection_string: str, database_name: str, collection_name: str) -> Optional[MongoCinemaWriter]:
    if not enabled:
        return None
    return MongoCinemaWriter(connection_string, database_name, collection_name)
