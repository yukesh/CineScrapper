from typing import Optional

from cinescrapper.cine_model import CineInfo
from cinescrapper.logger import get_logger

logger = get_logger()


class MongoCinemaWriter:
    """
    Writes cinema documents to MongoDB using an upsert keyed by title and year.
    """

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
            raise RuntimeError(
                "MongoDB support requires pymongo. Install project dependencies before using --mongo-enabled."
            ) from exception
        return MongoClient(connection_string)

    @staticmethod
    def _upsert_filter(cinema: CineInfo):
        if cinema.ref:
            return {"ref": cinema.ref}
        return {"title": cinema.title, "year": cinema.year}

    def upsert_cinema(self, cinema: CineInfo):
        document = cinema.to_dict()
        result = self._collection.update_one(
            self._upsert_filter(cinema),
            {"$set": document},
            upsert=True,
        )
        logger.debug("MongoDB upsert result for %s: %s", cinema.title, result.raw_result)
        return result

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
    return MongoCinemaWriter(connection_string, database_name, collection_name)
