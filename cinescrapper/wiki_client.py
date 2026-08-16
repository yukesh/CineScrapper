import os
import time

import random
import requests
from bs4 import BeautifulSoup

from cinescrapper import cine_helper
from cinescrapper.logger import get_logger

logger = get_logger()


class WikiClient:

    def __init__(self, base_url="https://en.wikipedia.org", sleep_time=None):
        self._base_url = base_url
        self._sleep_time = sleep_time
        self._session = requests.Session()
        logger.debug("Initializing the WikiClient and BaseURL is %s", base_url)

    def call_wiki(self, link: str) -> str:
        """
        Fetch the HTML content of a Wikipedia page.

        This method builds the full Wikipedia URL using the base URL and the
        provided page link, waits for the configured sleep time (if any), and
        performs an HTTP GET request. The response content is returned as a
        string if successful, otherwise an empty string is returned.

        :param link: Relative Wikipedia page link (e.g., "Inception").
        :return: Raw HTML of the requested page as a string, or an empty string
                 if the request fails.
        :raises requests.exceptions.RequestException: Only internally caught;
                 logs error and returns an empty string instead of propagating.
        """
        if self._sleep_time is not None:
            wait = self._sleep_time + random.uniform(0.2, 0.8)
            time.sleep(wait)
            logger.debug("Waiting for %d seconds to perform the lookup")

        headers = {
            "User-Agent": "CineScrapper/1.0"
        }

        url = None
        try:
            url = self._base_url + str(link)
            logger.debug("Parsing to %s", url)
        except Exception as exception:
            logger.warning("Parsing to %s", url)
            logger.error("Exception while building url " + exception.__str__())

        if url is not None:
            try:
                response = self._session.get(url, headers=headers, timeout=10)
                response.raise_for_status()  # raises HTTPError for 4xx/5xx
                return response.text
            except requests.exceptions.RequestException as exception:
                logger.error("❌ Error fetching HTML from %s: %s", url, exception)
                return ""  # return empty string or None

    def fetch(self, link: str, name: str = None, request_type: str = None) -> str:
        """
        Check the input in the cache, if not found, make a call to the Wiki, then
        cache the response and return the raw HTML Page.
        :param link:
        :param name:
        :param request_type:
        :return:
        """
        _cache_dir = cine_helper.fetch_cache_dir(request_type)
        name = link if name is None else name
        # Clean the name by replacing '/' with '_'
        safe_name = name.replace("/", "_")
        _file_path = _cache_dir + safe_name + ".html"
        content = ""

        # Check cache file existence and age (7 days expiry)
        if os.path.isfile(_file_path):
            try:
                mtime = os.path.getmtime(_file_path)
                one_week_seconds = 7 * 24 * 60 * 60  # 7 days in seconds

                if time.time() - mtime > one_week_seconds:
                    logger.info("Cache file expired for %s. Deleting and refetching.", _file_path)
                    os.remove(_file_path)
                    content = "" # Force re-fetch
                else:
                    logger.debug("Found valid cache in %s", _file_path)
                    with open(_file_path, "r", encoding="utf-8") as file:
                        content = file.read()
            except OSError as e:
                # Handle cases where the file might be inaccessible or deleted concurrently
                logger.warning("Could not read/check cache file %s: %s", _file_path, e)
                content = "" # Force re-fetch

        if len(content) < 1:
            logger.debug("Calling Wiki...")
            content = self.call_wiki(link)
            if content is not None:
                # Ensure the directory exists
                os.makedirs(os.path.dirname(_cache_dir), exist_ok=True)
                logger.info("Caching the response to %s", _file_path)
                try:
                    with open(_file_path, "w", encoding="utf-8") as file:
                        file.write(content)
                except OSError as e:
                    # Handle cases where the file might be inaccessible or deleted concurrently
                    logger.warning("Could not write cache file %s: %s", _file_path, e)
        return content

    def fetch_soup(self, link: str, name: str = None, request_type: str = None) -> BeautifulSoup | None:
        """
        Check the input in the cache, if not found, make a call to the Wiki, then
        cache the response and return the raw HTML Page as BeautifulSoup instance.
        :param link:
        :param name:
        :param request_type:
        :return:
        """
        content = self.fetch(link, name, request_type)
        if len(content) > 0:
            return BeautifulSoup(content, "html.parser")
        return None
