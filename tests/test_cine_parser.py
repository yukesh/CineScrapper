from pathlib import Path

import pytest
from bs4 import BeautifulSoup

from cinescrapper import cine_parser
from cinescrapper.cine_model import CineInfo


MOVIE_CACHE_DIR = Path(__file__).resolve().parents[1] / "site_cache" / "movies"


def load_movie_page(name):
    return BeautifulSoup((MOVIE_CACHE_DIR / name).read_text(), "html.parser")


def test_parse_soundtrack_page_extracts_tracklist_from_music_section():
    soup = load_movie_page("Jailer_2.html")

    soundtrack = cine_parser.parse_soundtrack_page(soup)

    assert soundtrack.composer == "Anirudh Ravichander"
    assert len(soundtrack.tracks) == 2
    assert soundtrack.tracks[0].number == 1
    assert soundtrack.tracks[0].title == "Hukum Reloaded"
    assert soundtrack.tracks[0].lyrics == "Super Subu"
    assert soundtrack.tracks[0].singers == "Anirudh Ravichander"
    assert soundtrack.tracks[0].length == "1:31"


def test_parse_soundtrack_page_extracts_album_infobox_details():
    soup = load_movie_page("Jockey_(2026_film).html")

    soundtrack = cine_parser.parse_soundtrack_page(soup)

    assert soundtrack.album_name == "Jockey"
    assert soundtrack.composer == "Sakthi Balaji"
    assert len(soundtrack.tracks) == 4
    assert soundtrack.tracks[0].title == "Kapura Gethu – Promo song"


def test_parse_soundtrack_page_can_apply_to_cinema_model():
    soup = load_movie_page("Draupathi_2.html")
    cinema = CineInfo(title="Draupathi 2", year=2026)

    soundtrack = cine_parser.parse_soundtrack_page(soup, cinema)

    assert cinema.soundtrack == soundtrack
    assert cinema.soundtrack.album_name == "Draupathi 2"
    assert cinema.soundtrack.composer == "Ghibran Vaibodha"
    assert len(cinema.soundtrack.tracks) == 3


def test_to_dict_keeps_soundtrack_data_canonical():
    soup = load_movie_page("Aalambana.html")
    cinema = CineInfo(title="Aalambana", year=2026)

    cine_parser.parse_soundtrack_page(soup, cinema)
    cinema_dict = cinema.to_dict()

    assert set(cinema_dict.keys()) == {
        "title",
        "year",
        "director",
        "cast",
        "studio",
        "ref",
        "source",
        "soundtrack",
    }
    assert "album_name" not in cinema_dict
    assert "composer" not in cinema_dict
    assert "tracks" not in cinema_dict
    assert cinema_dict["soundtrack"]["composer"] == "Hiphop Tamizha"
    assert len(cinema_dict["soundtrack"]["tracks"]) == 2
    assert cinema_dict["soundtrack"]["tracks"][0]["title"] == "Eppa Paarthaalum"


def test_parse_soundtrack_page_handles_pages_without_tracks():
    soup = load_movie_page("Karuppu_Pulsar.html")

    soundtrack = cine_parser.parse_soundtrack_page(soup)

    assert soundtrack.composer == "Inbaraj Rajendran"
    assert soundtrack.tracks == []


def test_find_soundtrack_page_link_ignores_generic_album_links():
    soup = load_movie_page("Jockey_(2026_film).html")

    assert cine_parser.find_soundtrack_page_link(soup) is None


def test_find_soundtrack_page_link_finds_main_soundtrack_article():
    soup = load_movie_page("Parasakthi_(2026_film).html")

    assert cine_parser.find_soundtrack_page_link(soup) == "/wiki/Parasakthi_(soundtrack)"


class TestSoundtrackParserMovieSamples:
    MOVIE_SAMPLES = [
        (
            "Aalambana.html",
            {
                "album_name": None,
                "composer": "Hiphop Tamizha",
                "track_count": 2,
                "first_track": "Eppa Paarthaalum",
                "soundtrack_ref": None,
            },
        ),
        (
            "Draupathi_2.html",
            {
                "album_name": "Draupathi 2",
                "composer": "Ghibran Vaibodha",
                "track_count": 3,
                "first_track": "EmKoney",
                "soundtrack_ref": None,
            },
        ),
        (
            "Gandhi_Talks.html",
            {
                "album_name": "Gandhi Talks",
                "composer": "A. R. Rahman",
                "track_count": 25,
                "first_track": "Soneri Kirane",
                "soundtrack_ref": None,
            },
        ),
        (
            "Jailer_2.html",
            {
                "album_name": None,
                "composer": "Anirudh Ravichander",
                "track_count": 2,
                "first_track": "Hukum Reloaded",
                "soundtrack_ref": None,
            },
        ),
        (
            "Karuppu_Pulsar.html",
            {
                "album_name": None,
                "composer": "Inbaraj Rajendran",
                "track_count": 0,
                "first_track": None,
                "soundtrack_ref": None,
            },
        ),
        (
            "Parasakthi_(2026_film).html",
            {
                "album_name": None,
                "composer": "G. V. Prakash Kumar",
                "track_count": 0,
                "first_track": None,
                "soundtrack_ref": "/wiki/Parasakthi_(soundtrack)",
            },
        ),
    ]

    @pytest.mark.parametrize(("movie_page", "expected"), MOVIE_SAMPLES)
    def test_parse_cached_movie_soundtrack_samples(self, movie_page, expected):
        soup = load_movie_page(movie_page)

        soundtrack = cine_parser.parse_soundtrack_page(soup)

        assert soundtrack.album_name == expected["album_name"]
        assert soundtrack.composer == expected["composer"]
        assert len(soundtrack.tracks) == expected["track_count"]
        assert cine_parser.find_soundtrack_page_link(soup) == expected["soundtrack_ref"]

        if expected["first_track"] is not None:
            assert soundtrack.tracks[0].title == expected["first_track"]
