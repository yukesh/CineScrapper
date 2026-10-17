import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient

# Load .env from the same directory as this script
env_file = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_file)

uri = os.environ["MONGODB_URI"]

client = MongoClient(uri, serverSelectionTimeoutMS=5000)

try:
    client.admin.command("ping")
    print("MongoDB connection successful!")
finally:
    client.close()