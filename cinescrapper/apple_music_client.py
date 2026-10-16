"""Apple/iTunes Search API client with shared rate limiting and retries."""

from __future__ import annotations

import urllib.parse

import requests

from cinescrapper.logger import get_logger
from cinescrapper.rate_limiter import RateLimiter
from cinescrapper.retry import RetryableHttpError, parse_retry_after, run_with_retry

logger = get_logger()

HEADERS = {
    "User-Agent": "CineScrapper/0.2.0",
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
}


class AppleMusicClient:
    def __init__(self, rate_limiter: RateLimiter, max_retries: int = 3, timeout: float = 15.0):
        self._rate_limiter = rate_limiter
        self._max_retries = max_retries
        self._timeout = timeout
        self._session = requests.Session()

    def _request(self, url: str):
        def operation():
            self._rate_limiter.acquire()
            response = self._session.get(url, headers=HEADERS, timeout=self._timeout)
            if response.status_code == 200:
                return response
            if response.status_code in (429, 500, 502, 503, 504):
                raise RetryableHttpError(response.status_code, parse_retry_after(response.headers.get("Retry-After")))
            response.raise_for_status()
            return response

        try:
            return run_with_retry(operation, max_attempts=self._max_retries, retry_exceptions=(requests.RequestException,))
        except Exception as exc:
            logger.error("Apple Music request failed: %s", exc)
            return None

    def lookup(self, album_name, year=None, artist_name="Original Motion Picture Soundtrack", country="in"):
        query_parts = [album_name]
        if artist_name:
            query_parts.append(artist_name)
        if year:
            query_parts.append(str(year))
        term = urllib.parse.quote_plus(" ".join(query_parts))
        url = f"https://itunes.apple.com/search?term={term}&country={country}&entity=album&limit=5"
        response = self._request(url)
        if response is None:
            return None
        try:
            data = response.json()
        except ValueError:
            logger.warning("Unable to parse JSON response from iTunes.")
            return None
        if data.get("resultCount", 0) == 0:
            return None
        if year:
            for album in data["results"]:
                release_year = (album.get("releaseDate") or "")[:4]
                if release_year == str(year):
                    return self._to_result(album, release_year)
        album = data["results"][0]
        return self._to_result(album, (album.get("releaseDate") or "")[:4] or None)

    @staticmethod
    def _to_result(album, release_year):
        return {
            "albumName": album.get("collectionName"),
            "artistName": album.get("artistName"),
            "releaseYear": release_year,
            "appleMusicUrl": album.get("collectionViewUrl"),
        }


def get_apple_music_album_url(album_name, year=None, artist_name="Original Motion Picture Soundtrack", country="in"):
    """Backward-compatible convenience function."""
    from cinescrapper.rate_limiter import RateLimiter
    return AppleMusicClient(RateLimiter(2.0), max_retries=5).lookup(album_name, year, artist_name, country)
