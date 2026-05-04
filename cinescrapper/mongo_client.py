from pymongo import MongoClient as PyMongoClient
from cinescrapper.logger import get_logger


logger = get_logger()


class MongoClient:

    def __init__(self, uri: str, db_name: str):

        self._uri = uri
        self._db_name = db_name
        self._client = PyMongoClient(self._uri)
        self._db = self._client[self._db_name]
        logger.debug("Initialized MongoClient with URI: %s and DB: %s", uri, db_name)


    @classmethod
    def with_defaults(cls):
        """
        Create a MongoClient instance with default parameters.

        :return: MongoClient instance with default URI and database name.
        """
        return cls("mongodb://admin:password@192.168.0.50:27017/", "_wiki_album_info")


    def get_collection(self, collection_name: str):
        """
        Get a collection from the database.

        :param collection_name: Name of the collection to retrieve.
        :return: The requested collection.
        """
        return self._db[collection_name]