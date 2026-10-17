"""Wikipedia HTTP client with persistent cache, rate limiting and retries."""

from __future__ import annotations

import os
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from cinescrapper import cine_helper
from cinescrapper.logger import get_logger
from cinescrapper.rate_limiter import RateLimiter
from cinescrapper.retry import RetryableHttpError, parse_retry_after, run_with_retry

logger = get_logger()


class WikiClient:
    def __init__(self, base_url="https://en.wikipedia.org", rate_limiter=None, max_retries=3, timeout=15.0, cache_ttl_seconds=7 * 24 * 60 * 60):
        self._base_url = base_url
        self._rate_limiter = rate_limiter or RateLimiter(1.5)
        self._max_retries = max_retries
        self._timeout = timeout
        self._cache_ttl_seconds = cache_ttl_seconds
        self._session = requests.Session()

    def call_wiki(self, link: str) -> str:
        url = urljoin(self._base_url.rstrip("/") + "/", str(link))
        headers = {"User-Agent": "CineScrapper/0.2.0"}

        def operation():
            self._rate_limiter.acquire()
            response = self._session.get(url, headers=headers, timeout=self._timeout)
            if response.status_code == 200:
                return response.text
            if response.status_code in (429, 500, 502, 503, 504):
                raise RetryableHttpError(response.status_code, parse_retry_after(response.headers.get("Retry-After")))
            response.raise_for_status()
            return response.text

        try:
            return run_with_retry(operation, max_attempts=self._max_retries, retry_exceptions=(requests.RequestException,))
        except Exception as exc:
            logger.error("Error fetching HTML from %s: %s", url, exc)
            return ""

    def fetch(self, link: str, name: str = None, request_type: str = None) -> str:
        cache_dir = cine_helper.fetch_cache_dir(request_type)
        name = link if name is None else name
        safe_name = str(name).replace("/", "_").replace("\\", "_")
        file_path = os.path.join(cache_dir, safe_name + ".html")

        if os.path.isfile(file_path):
            try:
                age = time.time() - os.path.getmtime(file_path)
                if age <= self._cache_ttl_seconds:
                    logger.debug("Found valid cache in %s", file_path)
                    with open(file_path, "r", encoding="utf-8") as file:
                        return file.read()
                logger.info("Cache expired for %s. Refetching.", file_path)
                os.remove(file_path)
            except OSError as exc:
                logger.warning("Could not read/check cache file %s: %s", file_path, exc)

        content = self.call_wiki(link)
        if content:
            try:
                os.makedirs(cache_dir, exist_ok=True)
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(content)
            except OSError as exc:
                logger.warning("Could not write cache file %s: %s", file_path, exc)
        return content

    def fetch_soup(self, link: str, name: str = None, request_type: str = None) -> BeautifulSoup | None:
        content = self.fetch(link, name, request_type)
        return BeautifulSoup(content, "html.parser") if content else None
