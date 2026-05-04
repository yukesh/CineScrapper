import pytest
from cinescrapper.scrapper import find_cinema


@pytest.mark.integraion
def test_find_cinema():
    """
    Integration test for find_cinema function.
    """
    master_wiki_page = "Lists_of_Tamil-language_films"
    year = 2025

    cinemas = find_cinema(master_wiki_page, year)

    assert cinemas is not None, "No cinemas found"
    assert len(cinemas) > 0, "Cinemas dictionary is empty"

    # Check for a known cinema entry
    expected_title = "List of Tamil films of 2025"
    assert expected_title in cinemas, f"{expected_title} not found in cinemas"

    href = cinemas[expected_title]
    print(f"Cinema Title: {expected_title}, Href: {href}")

    assert href.startswith("/wiki/"), "Href does not start with /wiki/"


@pytest.mark.integration
def test_load_sound_track():
    """
    Integration test for load_sound_track function.
    """
    from cinescrapper.scrapper import load_sound_track

    title = "Thalaivan Thalaivii"
    year = 2025
    ref_link = "/wiki/Thalaivan_Thalaivii"

    try:
        load_sound_track(title, year, ref_link)
    except Exception as e:
        pytest.fail(f"load_sound_track raised an exception: {e}")