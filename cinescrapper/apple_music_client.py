import time
import random
import requests
import urllib.parse
from cinescrapper.logger import get_logger

logger = get_logger()

def get_random_headers():
    chrome_version = random.randint(110, 124)
    return {
        "User-Agent": (
            f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            f"AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{chrome_version}.0.{random.randint(1000, 9999)}.120 "
            "Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Language": random.choice([
            "en-US,en;q=0.9",
            "en-GB,en;q=0.8",
            "en-IN,en;q=0.8"
        ]),
        "Connection": "keep-alive"
    }


def fetch_with_retry(url, retries=3, timeout=10):
    response = None
    delay = 2

    for attempt in range(retries):
        headers = get_random_headers()  # new header each attempt
        response = requests.get(url, headers=headers, timeout=timeout)

        if response.status_code == 200:
            return response

        # Handle anti-bot rate limit
        if response.status_code in (403, 429):
            logger.warning("Rate-limited, sleeping for %s seconds", delay)
            time.sleep(delay)
            delay *= 2  # exponential backoff
            continue

        logger.warning("Attempt %d failed: %s", attempt + 1, response.status_code)
        time.sleep(1)

    return response


def get_apple_music_album_url(album_name, year=None, album_type="Original Motion Picture Soundtrack", country="in"):
    """
    Fetch Apple Music album URL using iTunes Search API.

    :param album_name: Album name (string)
    :param album_type: Optional Album name (string)
    :param year: Optional release year (integer or string)
    :param country: Storefront country code (default 'us')
    :return: Apple Music album URL or None
    """
    # Build search query
    query_parts = [album_name]
    if album_type:
        query_parts.append(album_type)
    if year:
        query_parts.append(str(year))
    query = " ".join(query_parts)

    # Encode for URL
    term = urllib.parse.quote_plus(query)

    # iTunes Search API endpoint
    url = f"https://itunes.apple.com/search?term={term}&country={country}&entity=album&limit=5"
    logger.debug("Calling iTunes API with URL: %s", url)

    # Call API
    #response = requests.get(url, headers=headers, timeout=10)
    response = fetch_with_retry(url, retries=3, timeout=10)
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

