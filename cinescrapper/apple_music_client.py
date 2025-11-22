import requests
import urllib.parse
from cinescrapper.logger import get_logger

logger = get_logger()


def get_apple_music_album_url(album_name, year=None, artist_name="Original Motion Picture Soundtrack", country="in"):
    """
    Fetch Apple Music album URL using iTunes Search API.

    :param album_name: Album name (string)
    :param artist_name: Optional artist name (string)
    :param year: Optional release year (integer or string)
    :param country: Storefront country code (default 'us')
    :return: Apple Music album URL or None
    """
    # Build search query
    query_parts = [album_name]
    if artist_name:
        query_parts.append(artist_name)
    if year:
        query_parts.append(str(year))
    query = " ".join(query_parts)

    # Encode for URL
    term = urllib.parse.quote_plus(query)

    # iTunes Search API endpoint
    url = f"https://itunes.apple.com/search?term={term}&country={country}&entity=album&limit=5"
    logger.debug("Calling iTunes API with URL: %s", url)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                      "AppleWebKit/537.36 (KHTML, like Gecko) "
                      "Chrome/117.0.0.0 Safari/537.36",
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive"
    }

    # Call API
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        logger.warning("Error fetching data: %s", response.status_code)
        logger.debug("Response: %s", response.text)
        return None

    data = response.json()

    if data.get("resultCount", 0) == 0:
        logger.debug("No albums found.")
        return None

    # Pick the best-matching album (if multiple, prefer one matching the year)
    for album in data["results"]:
        release_date = album.get("releaseDate", "")
        release_year = release_date[:4] if release_date else None
        if year and release_year == str(year):
            return {
                "albumName": album.get("collectionName"),
                "artistName": album.get("artistName"),
                "releaseYear": release_year,
                "appleMusicUrl": album.get("collectionViewUrl")
            }

    # Fallback: return the first result if no exact year match
    album = data["results"][0]
    release_year = album.get("releaseDate", "")[:4] if album.get("releaseDate") else None
    return {
        "albumName": album.get("collectionName"),
        "artistName": album.get("artistName"),
        "releaseYear": release_year,
        "appleMusicUrl": album.get("collectionViewUrl")
    }
