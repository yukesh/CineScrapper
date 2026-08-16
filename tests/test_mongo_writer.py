from cinescrapper.cine_model import CineInfo, SoundtrackInfo, TrackInfo
from cinescrapper.mongo_writer import MongoCinemaWriter, create_mongo_writer


class FakeUpdateResult:
    raw_result = {"ok": 1}


class FakeCollection:
    def __init__(self):
        self.calls = []

    def update_one(self, filter_doc, update_doc, upsert=False):
        self.calls.append(
            {
                "filter_doc": filter_doc,
                "update_doc": update_doc,
                "upsert": upsert,
            }
        )
        return FakeUpdateResult()


def test_create_mongo_writer_returns_none_when_disabled():
    writer = create_mongo_writer(False, "mongodb://example.invalid", "db", "collection")

    assert writer is None


def test_upsert_cinema_uses_ref_when_available():
    collection = FakeCollection()
    writer = MongoCinemaWriter(
        "mongodb://example.invalid",
        "db",
        "collection",
        collection=collection,
    )
    cinema = CineInfo(title="Aalambana", year=2026, ref="/wiki/Aalambana")
    cinema.soundtrack = SoundtrackInfo(
        composer="Hiphop Tamizha",
        tracks=[TrackInfo(number=1, title="Eppa Paarthaalum")],
    )

    writer.upsert_cinema(cinema)

    assert collection.calls == [
        {
            "filter_doc": {"ref": "/wiki/Aalambana"},
            "update_doc": {
                "$set": {
                    "title": "Aalambana",
                    "year": 2026,
                    "director": None,
                    "cast": [],
                    "studio": None,
                    "ref": "/wiki/Aalambana",
                    "source": [],
                    "soundtrack": {
                        "album_name": None,
                        "composer": "Hiphop Tamizha",
                        "ref": None,
                        "tracks": [
                            {
                                "number": 1,
                                "title": "Eppa Paarthaalum",
                                "lyrics": None,
                                "singers": None,
                                "length": None,
                            }
                        ],
                    },
                }
            },
            "upsert": True,
        }
    ]


def test_upsert_cinema_falls_back_to_title_and_year():
    collection = FakeCollection()
    writer = MongoCinemaWriter(
        "mongodb://example.invalid",
        "db",
        "collection",
        collection=collection,
    )
    cinema = CineInfo(title="Aalambana", year=2026)

    writer.upsert_cinema(cinema)

    assert collection.calls[0]["filter_doc"] == {"title": "Aalambana", "year": 2026}
    assert collection.calls[0]["upsert"] is True
