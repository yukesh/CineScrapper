from types import ModuleType, SimpleNamespace
import sys

# The overlay is applied to the existing repository, where cine_model.py exists.
# This stub keeps this isolated overlay test runnable on its own as well.
if "cinescrapper.cine_model" not in sys.modules:
    model_module = ModuleType("cinescrapper.cine_model")
    model_module.CineInfo = object
    sys.modules["cinescrapper.cine_model"] = model_module

from cinescrapper.mongo_writer import MongoCinemaWriter


class FakeCollection:
    def __init__(self, initial=None):
        self.document = dict(initial) if initial else None
        self.calls = []

    def find_one(self, query):
        if self.document is None:
            return None
        if all(self.document.get(key) == value for key, value in query.items()):
            return dict(self.document)
        return None

    def update_one(self, query, update, upsert=False):
        self.calls.append((query, update, upsert))
        if self.document is None:
            self.document = {**query, **update.get("$set", {})}
            return SimpleNamespace(raw_result={"upserted": True})
        self.document.update(update.get("$set", {}))
        return SimpleNamespace(raw_result={"modified": True})


class Cinema:
    def __init__(self, title="Film", year=2024, url="url-a"):
        self.title, self.year, self.ref, self.url = title, year, "/wiki/Film", url

    def to_dict(self):
        return {"title": self.title, "year": self.year, "ref": self.ref, "url": self.url}


def writer_for(collection):
    return MongoCinemaWriter("unused", "unused", "unused", collection=collection)


def test_inserts_new_movie():
    collection = FakeCollection()
    assert writer_for(collection).save_cinema(Cinema()) == "inserted"
    assert len(collection.calls) == 1
    assert collection.calls[0][2] is True


def test_skips_write_when_document_is_unchanged():
    collection = FakeCollection(Cinema().to_dict() | {"_id": "mongo-id"})
    assert writer_for(collection).save_cinema(Cinema()) == "unchanged"
    assert collection.calls == []


def test_updates_changed_movie():
    collection = FakeCollection(Cinema(url="old-url").to_dict())
    assert writer_for(collection).save_cinema(Cinema(url="new-url")) == "updated"
    assert len(collection.calls) == 1
    assert collection.calls[0][2] is False
    assert collection.document["url"] == "new-url"
