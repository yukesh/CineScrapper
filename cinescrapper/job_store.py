"""Mongo-backed job and item state for restartable scraper runs."""

from __future__ import annotations

from datetime import datetime, timezone

from cinescrapper.logger import get_logger

logger = get_logger()


class MongoJobStore:
    def __init__(self, collection):
        self._jobs = collection.database["scrape_jobs"]
        self._items = collection.database["scrape_items"]
        self._jobs.create_index("job_id", unique=True)
        self._items.create_index([("job_id", 1), ("item_id", 1)], unique=True)

    def start_job(self, job_id, year, total):
        now = datetime.now(timezone.utc)
        self._jobs.update_one(
            {"job_id": job_id},
            {"$set": {"year": year, "total": total, "status": "RUNNING", "started_at": now, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )

    def is_completed(self, job_id, item_id):
        doc = self._items.find_one({"job_id": job_id, "item_id": item_id, "status": "COMPLETED"}, {"_id": 1})
        return doc is not None

    def mark_completed(self, job_id, item_id):
        now = datetime.now(timezone.utc)
        self._items.update_one({"job_id": job_id, "item_id": item_id}, {"$set": {"status": "COMPLETED", "updated_at": now}}, upsert=True)

    def mark_failed(self, job_id, item_id, error):
        now = datetime.now(timezone.utc)
        self._items.update_one(
            {"job_id": job_id, "item_id": item_id},
            {"$set": {"status": "FAILED", "error": str(error), "updated_at": now}, "$inc": {"attempts": 1}},
            upsert=True,
        )

    def finish_job(self, job_id, status, stats):
        self._jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": status, "finished_at": datetime.now(timezone.utc), "stats": stats, "updated_at": datetime.now(timezone.utc)}},
        )


def item_id_for(cinema):
    return cinema.ref or f"{cinema.year}:{cinema.title}"
