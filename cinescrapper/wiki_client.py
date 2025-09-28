import os
import time

import requests

from cinescrapper import cine_helper
from cinescrapper.logger import get_logger
from bs4 import BeautifulSoup

logger = get_logger()


class WikiClient:

    def __init__(self, base_url="https://en.wikipedia.org", sleep_time=None):
        self._base_url = base_url
        self._sleep_time = sleep_time
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
            time.sleep(self._sleep_time)
            logger.debug("Waiting for %d seconds to perform the lookup")

        headers = {
            "User-Agent": "CineScrapper/1.0"
        }

        url = None
        try:
            url = self._base_url + str(link)
            logger.debug("Parsing to %s", url)
        except Exception as exception:
            logger.warn("Parsing to %s", url)
            logger.error("Exception while building url " + exception.__str__())

        if url is not None:
            try:
                response = requests.get(url, headers=headers, timeout=10)
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
        _file_path = _cache_dir + name + ".html"
        content = ""
        if os.path.isfile(_file_path):
            logger.debug("Found in cache %s", _file_path)
            with open(_file_path, "r") as file:
                content = file.read()

        if len(content) < 1:
            logger.debug("Calling Wiki...")
            content = self.call_wiki(link)
            if content is not None:
                with open(_file_path, "w") as file:
                    file.write(content)
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
