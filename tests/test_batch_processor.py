from types import SimpleNamespace

import pytest

from cinescrapper.batch_processor import BatchProcessor, BatchProcessingError, chunks


def test_chunks():
    assert list(chunks(list(range(5)), 2)) == [[0, 1], [2, 3], [4]]


def test_batch_processor_continues_after_failure():
    movies = [SimpleNamespace(title="one", ref="one", year=2026), SimpleNamespace(title="two", ref="two", year=2026)]

    class Processor:
        def process(self, movie):
            if movie.title == "one":
                raise RuntimeError("boom")
            return movie

    class Writer:
        def __init__(self): self.saved = []
        def upsert_cinema(self, movie): self.saved.append(movie.title)

    writer = Writer()
    with pytest.raises(BatchProcessingError):
        BatchProcessor(Processor(), writer, batch_size=1).process(movies, "job", 2026)
    assert writer.saved == ["two"]


def test_completed_items_are_reprocessed_by_default_but_skipped_with_resume():
    movie = SimpleNamespace(title="already-done", ref="already-done", year=2026)

    class Processor:
        def __init__(self):
            self.calls = 0

        def process(self, value):
            self.calls += 1
            return value

    class JobStore:
        def start_job(self, *args): pass
        def is_completed(self, job_id, item_id): return True
        def mark_completed(self, *args): pass
        def finish_job(self, *args): pass

    processor = Processor()
    BatchProcessor(processor, job_store=JobStore()).process([movie], "job", 2026)
    assert processor.calls == 1

    processor = Processor()
    stats = BatchProcessor(processor, job_store=JobStore(), resume=True).process([movie], "job", 2026)
    assert processor.calls == 0
    assert stats.skipped == 1
