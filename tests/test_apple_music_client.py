import unittest
import pytest
from cinescrapper.apple_music_client import get_apple_music_album_url


@pytest.mark.integration
def test_album_real_call():
    """
    Integration test for get_apple_music_album_url with a real API call.
    """
    result = get_apple_music_album_url(
        album_name="Star",
        album_type="Original Motion Picture Soundtrack",
        year=2024
    )
    assert result is not None, "No album found from API"

    var = result["appleMusicUrl"]  # Print the URL for verification
    print(f"Apple Music URL: {var}")

    assert "Star" in result["albumName"]
    assert result["releaseYear"] == "2024"
    assert result["appleMusicUrl"].startswith("https://music.apple.com/")

