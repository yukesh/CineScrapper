"""Batch orchestration for restartable, rate-limited movie processing."""

from __future__ import annotations

from dataclasses import dataclass

from cinescrapper.job_store import item_id_for
from cinescrapper.logger import get_logger

logger = get_logger()


@dataclass
class BatchStats:
    total: int = 0
    skipped: int = 0
    processed: int = 0
    failed: int = 0


class BatchProcessingError(RuntimeError):
    pass


def chunks(items, size):
    for start in range(0, len(items), size):
        yield items[start:start + size]


class BatchProcessor:
    def __init__(self, movie_processor, mongo_writer=None, job_store=None, batch_size=10, force=False):
        self.movie_processor = movie_processor
        self.mongo_writer = mongo_writer
        self.job_store = job_store
        self.batch_size = batch_size
        self.force = force

    def process(self, movies, job_id, year):
        stats = BatchStats(total=len(movies))
        if self.job_store:
            self.job_store.start_job(job_id, year, len(movies))

        for batch_number, batch in enumerate(chunks(movies, self.batch_size), 1):
            logger.info("Starting batch %d (%d movies)", batch_number, len(batch))
            for cinema in batch:
                item_id = item_id_for(cinema)
                if self.job_store and not self.force and self.job_store.is_completed(job_id, item_id):
                    stats.skipped += 1
                    logger.info("Skipping completed movie: %s", cinema.title)
                    continue
                try:
                    processed = self.movie_processor.process(cinema)
                    if self.mongo_writer:
                        self.mongo_writer.upsert_cinema(processed)
                    if self.job_store:
                        self.job_store.mark_completed(job_id, item_id)
                    stats.processed += 1
                except Exception as exc:
                    stats.failed += 1
                    logger.exception("Movie failed: %s", cinema.title)
                    if self.job_store:
                        self.job_store.mark_failed(job_id, item_id, exc)
            logger.info("Completed batch %d; processed=%d skipped=%d failed=%d", batch_number, stats.processed, stats.skipped, stats.failed)

        status = "COMPLETED" if stats.failed == 0 else "COMPLETED_WITH_ERRORS"
        if self.job_store:
            self.job_store.finish_job(job_id, status, vars(stats))
        if stats.failed:
            raise BatchProcessingError(f"{stats.failed} movie(s) failed; see scrape_items for details")
        return stats
