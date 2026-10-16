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
