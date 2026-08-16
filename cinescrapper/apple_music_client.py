import random
import time
import urllib.parse

import requests

from cinescrapper.logger import get_logger

logger = get_logger()

# Reuse a single session for all requests
session = requests.Session()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/117.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# Minimum delay between consecutive API calls (seconds)
REQUEST_INTERVAL = 2.0

# Maximum retry attempts when throttled or server errors occur
MAX_RETRIES = 5

_last_request_time = 0.0


def _throttle():
    """
    Ensure we don't bombard the iTunes Search API.
    """
    global _last_request_time

    elapsed = time.time() - _last_request_time

    if elapsed < REQUEST_INTERVAL:
        wait = REQUEST_INTERVAL - elapsed
        logger.debug("Throttling request for %.2f seconds", wait)
        time.sleep(wait)

    _last_request_time = time.time()


def _call_itunes_api(url):
    """
    Calls iTunes Search API with retry and exponential backoff.

    Retries on:
      - HTTP 429 (Too Many Requests)
      - HTTP 500/502/503/504
      - Network exceptions

    Returns:
        requests.Response or None
    """

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            _throttle()

            logger.debug("Calling iTunes API: %s", url)

            response = session.get(
                url,
                headers=HEADERS,
                timeout=10,
            )

            if response.status_code == 200:
                return response

            # Handle rate limiting
            if response.status_code == 429:

                retry_after = response.headers.get("Retry-After")

                if retry_after:
                    try:
                        wait = int(retry_after)
                    except ValueError:
                        wait = 5
                else:
                    # Exponential backoff with random jitter
                    wait = min((2 ** attempt) + random.uniform(0.5, 2.0), 60)

                logger.warning(
                    "Rate limit exceeded (HTTP 429). "
                    "Attempt %d/%d. Retrying after %.1f seconds.",
                    attempt,
                    MAX_RETRIES,
                    wait,
                )

                logger.debug("Response: %s", response.text)

                time.sleep(wait)
                continue

            # Retry transient server errors
            if response.status_code in (500, 502, 503, 504):

                wait = min(2 ** attempt, 30)

                logger.warning(
                    "Server error %d. Attempt %d/%d. "
                    "Retrying after %d seconds.",
                    response.status_code,
                    attempt,
                    MAX_RETRIES,
                    wait,
                )

                time.sleep(wait)
                continue

            # Non-retryable error
            logger.warning("Error fetching data: %s", response.status_code)
            logger.debug("Response: %s", response.text)
            return None

        except requests.exceptions.Timeout:

            wait = min(2 ** attempt, 30)

            logger.warning(
                "Request timed out. Attempt %d/%d. "
                "Retrying after %d seconds.",
                attempt,
                MAX_RETRIES,
                wait,
            )

            time.sleep(wait)

        except requests.exceptions.RequestException as ex:

            wait = min(2 ** attempt, 30)

            logger.warning(
                "Network error: %s. Attempt %d/%d. "
                "Retrying after %d seconds.",
                ex,
                attempt,
                MAX_RETRIES,
                wait,
            )

            time.sleep(wait)

    logger.error("Maximum retry attempts exhausted.")
    return None


def get_apple_music_album_url(
    album_name,
    year=None,
    artist_name="Original Motion Picture Soundtrack",
    country="in",
):
    """
    Fetch Apple Music album URL using iTunes Search API.

    :param album_name: Album name
    :param artist_name: Optional artist name
    :param year: Optional release year
    :param country: Storefront country code
    :return: Dictionary containing album details or None
    """

    query_parts = [album_name]

    if artist_name:
        query_parts.append(artist_name)

    if year:
        query_parts.append(str(year))

    query = " ".join(query_parts)

    term = urllib.parse.quote_plus(query)

    url = (
        "https://itunes.apple.com/search"
        f"?term={term}"
        f"&country={country}"
        "&entity=album"
        "&limit=5"
    )

    response = _call_itunes_api(url)

    if response is None:
        return None

    try:
        data = response.json()
    except ValueError:
        logger.warning("Unable to parse JSON response from iTunes.")
        return None

    if data.get("resultCount", 0) == 0:
        logger.debug("No albums found for '%s'", album_name)
        return None

    # Prefer exact release year match
    if year:
        for album in data["results"]:

            release_date = album.get("releaseDate", "")
            release_year = release_date[:4] if release_date else None

            if release_year == str(year):

                return {
                    "albumName": album.get("collectionName"),
                    "artistName": album.get("artistName"),
                    "releaseYear": release_year,
                    "appleMusicUrl": album.get("collectionViewUrl"),
                }

    # Fallback to first result
    album = data["results"][0]

    release_date = album.get("releaseDate", "")
    release_year = release_date[:4] if release_date else None

    return {
        "albumName": album.get("collectionName"),
        "artistName": album.get("artistName"),
        "releaseYear": release_year,
        "appleMusicUrl": album.get("collectionViewUrl"),
    }