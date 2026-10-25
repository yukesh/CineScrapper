"""Manually verify the configured MongoDB connection. Run with python -m cinescrapper.test_mongo."""

import os

from pymongo import MongoClient

from cinescrapper.env import load_project_env


def main() -> int:
    load_project_env()
    uri = os.getenv("CINESCRAPPER_MONGO_URI") or os.getenv("MONGODB_URI")
    if not uri:
        raise RuntimeError(
            "MongoDB URI missing. Set CINESCRAPPER_MONGO_URI or MONGODB_URI "
            "in the project-root .env file."
        )

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        print("MongoDB connection successful!")
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
