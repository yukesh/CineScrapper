"""Process one discovered movie independently of batch orchestration."""

from __future__ import annotations

from cinescrapper import apple_music_client, cine_constants, cine_parser
from cinescrapper.cine_model import CineInfo, SourceInfo
from cinescrapper.logger import get_logger

logger = get_logger()


def get_soundtrack_page_name(raw_href):
    if raw_href and isinstance(raw_href, str) and raw_href.startswith("/wiki/"):
        return raw_href[len("/wiki/"):]
    return raw_href


class MovieProcessor:
    def __init__(self, wiki_client, apple_music):
        self.wiki_client = wiki_client
        self.apple_music = apple_music

    def process(self, cinema: CineInfo) -> CineInfo:
        if not cinema.title:
            raise ValueError("Movie title is missing")

        logger.info("Processing movie: %s (%s)", cinema.title, cinema.year)
        movie_soup = None
        if cinema.ref:
            movie_soup = self.wiki_client.fetch_soup(
                cinema.ref,
                get_soundtrack_page_name(cinema.ref),
                cine_constants.TYPE_MOVIE,
            )

        if movie_soup is not None:
            cine_parser.parse_soundtrack_page(movie_soup, cinema)
            soundtrack_ref = cine_parser.find_soundtrack_page_link(movie_soup)
            if soundtrack_ref:
                soundtrack_soup = self.wiki_client.fetch_soup(
                    soundtrack_ref,
                    get_soundtrack_page_name(soundtrack_ref),
                    cine_constants.TYPE_SOUNDTRACK,
                )
                if soundtrack_soup is not None:
                    soundtrack = cine_parser.parse_soundtrack_page(soundtrack_soup, cinema)
                    soundtrack.ref = soundtrack_ref
        else:
            logger.warning("Wikipedia movie page unavailable for %s", cinema.title)

        result = self.apple_music.lookup(cinema.title, cinema.year)
        if result:
            cinema.add_source(SourceInfo("Apple Music", result.get("appleMusicUrl")))
            logger.info("Found Apple Music Album: %s by %s", result.get("albumName"), result.get("artistName"))
        else:
            logger.warning("No Apple Music Album found for: %s", cinema.title)

        return cinema
