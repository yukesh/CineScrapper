"""Application-level discovery and scrape orchestration."""

from __future__ import annotations

import re

from cinescrapper import cine_constants, cine_helper, cine_parser
from cinescrapper.batch_processor import BatchProcessor
from cinescrapper.cine_model import CineInfo
from cinescrapper.job_store import MongoJobStore
from cinescrapper.logger import get_logger
from cinescrapper.movie_processor import MovieProcessor
from cinescrapper.rate_limiter import RateLimiter
from cinescrapper.wiki_client import WikiClient
from cinescrapper.apple_music_client import AppleMusicClient

logger = get_logger()


def clean_wiki_link(raw_href):
    if raw_href and isinstance(raw_href, str) and raw_href.startswith("//en.wikipedia.org/"):
        return raw_href[len("/en.wikipedia.org/"):]
    return raw_href


def find_cinemas(_master_wiki_page: str, _start_year: int, _end_year: int = None, _condition: str = None, wiki_client: WikiClient | None = None):
    client = wiki_client or WikiClient()
    soup = client.fetch_soup("/wiki/" + _master_wiki_page, _master_wiki_page)
    div_tag = soup.find("div", {"id": "mw-content-text"}) if soup is not None else None
    cinemas = {}
    if div_tag is None:
        logger.info("No Div Tag Found for Cinemas")
        return cinemas
    a_tags = div_tag.find_all("a", title=re.compile("List of Tamil films", re.I))
    for a in a_tags:
        title = a.get("title")
        year = int(cine_helper.find_year(title))
        matches = (
            (_condition == "gtr" and year > _start_year)
            or (_condition == "ltr" and year < _start_year)
            or (_condition is None and _start_year == year)
            or (_start_year is not None and _end_year is not None and _start_year < year < _end_year)
        )
        if matches:
            cinemas[title] = clean_wiki_link(a.get("href"))
    return cinemas


def find_cinema(_master_wiki_page, _year, wiki_client: WikiClient | None = None):
    return find_cinemas(_master_wiki_page, _year, wiki_client=wiki_client)


def find_cinemas_greater(_master_wiki_page, _year):
    return find_cinemas(_master_wiki_page, _year, None, "gtr")


def find_cinemas_lesser(_master_wiki_page, _year):
    return find_cinemas(_master_wiki_page, _year, None, "ltr")


def discover_movies(master_wiki_page: str, year: int, wiki_client: WikiClient | None = None) -> list[CineInfo]:
    """Discover and parse all movie rows without doing per-movie enrichment."""
    cinemas = find_cinema(master_wiki_page, year, wiki_client)
    if not cinemas:
        return []
    client = wiki_client or WikiClient()
    movies: list[CineInfo] = []
    for title, ref_link in cinemas.items():
        soup = client.fetch_soup(ref_link, title)
        if soup is None:
            logger.warning("Unable to fetch yearly movie-list page: %s", title)
            continue
        for wikitable in soup.find_all("table", {"class": "wikitable"}):
            rows = cine_parser.parse_table(wikitable, int(cine_helper.find_year(title)))
            movies.extend(movie for movie in rows if movie.title)
    logger.info("Discovered %d movies for %d", len(movies), year)
    return movies


def scrape_cinemas(_master_wiki_page: str, _year: int, mongo_writer=None, config=None, end_year: int | None = None):
    """Scrape one year or an inclusive range of years in ascending order."""
    from cinescrapper.config import ScraperConfig
    config = config or ScraperConfig.from_env()
    config.validate()

    if end_year is not None and _year > end_year:
        raise ValueError("start year must be less than or equal to end year")
    years = range(_year, (end_year if end_year is not None else _year) + 1)
    results = {}

    wiki_limiter = RateLimiter(config.wiki_rate_limit, config.rate_limit_jitter)
    apple_limiter = RateLimiter(config.apple_music_rate_limit, config.rate_limit_jitter)
    wiki_client = WikiClient(
        rate_limiter=wiki_limiter,
        max_retries=config.max_retries,
        timeout=config.request_timeout,
        cache_ttl_seconds=config.cache_ttl_seconds,
    )
    apple_client = AppleMusicClient(apple_limiter, config.max_retries, config.request_timeout)
    processor = MovieProcessor(wiki_client, apple_client)

    for year in years:
        logger.info("Starting scrape for year %d", year)
        movies = discover_movies(_master_wiki_page, year, wiki_client)
        if not movies:
            logger.warning("No movies discovered for year %s", year)
            results[year] = None
            continue

        job_store = MongoJobStore(mongo_writer._collection) if mongo_writer is not None else None
        batch_processor = BatchProcessor(
            processor,
            mongo_writer=mongo_writer,
            job_store=job_store,
            batch_size=config.batch_size,
            force=config.force,
            resume=config.resume,
        )
        job_id = f"{_master_wiki_page}:{year}:v0.2.0"
        try:
            results[year] = batch_processor.process(movies, job_id, year)
        except Exception:
            if end_year is None:
                raise
            logger.exception("Scraping year %d failed; continuing with subsequent years", year)
            results[year] = None

    completed_stats = [value for value in results.values() if value is not None]
    if completed_stats:
        totals = {
            key: sum(getattr(value, key, 0) for value in completed_stats)
            for key in ("total", "processed", "inserted", "updated", "unchanged", "skipped", "failed")
        }
        logger.info("Year-range totals: %s", totals)
    logger.info("Year-range scrape finished: %d year(s) attempted", len(results))
    return results[_year] if end_year is None else results
