from datetime import date
import argparse

from cinescrapper import __version__
from cinescrapper.config import ScraperConfig
from cinescrapper.mongo_writer import create_mongo_writer
from cinescrapper.scrapper import scrape_cinemas
from cinescrapper.logger import setup_logger, get_logger


def main():
    parser = argparse.ArgumentParser(description="CineScrapper: Scrape cinema data from Wikipedia.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--wiki-source", default="Lists_of_Tamil-language_films")
    parser.add_argument("--year", type=int, default=date.today().year)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--wiki-rate-limit", type=float, default=None, help="Minimum seconds between Wikipedia requests")
    parser.add_argument("--apple-music-rate-limit", type=float, default=None, help="Minimum seconds between Apple/iTunes requests")
    parser.add_argument("--rate-limit-jitter", type=float, default=None)
    parser.add_argument("--max-retries", type=int, default=None)
    parser.add_argument("--retry-base-delay", type=float, default=None)
    parser.add_argument("--retry-max-delay", type=float, default=None)
    parser.add_argument("--cache-ttl", type=int, default=None, help="Wikipedia cache TTL in seconds")
    parser.add_argument("--request-timeout", type=float, default=None)
    parser.add_argument("--force", action="store_true", help="Reprocess movies already marked completed for this job")
    parser.add_argument("--mongo-enabled", action="store_true")
    parser.add_argument("--mongo-uri", default="mongodb://localhost:27017")
    parser.add_argument("--mongo-db", default="cinescrapper")
    parser.add_argument("--mongo-collection", default="cinemas")
    args = parser.parse_args()

    setup_logger(args.log_level)
    logger = get_logger()
    config = ScraperConfig.from_env()
    overrides = {
        "batch_size": args.batch_size,
        "wiki_rate_limit": args.wiki_rate_limit,
        "apple_music_rate_limit": args.apple_music_rate_limit,
        "rate_limit_jitter": args.rate_limit_jitter,
        "max_retries": args.max_retries,
        "retry_base_delay": args.retry_base_delay,
        "retry_max_delay": args.retry_max_delay,
        "cache_ttl_seconds": args.cache_ttl,
        "request_timeout": args.request_timeout,
        "force": True if args.force else None,
    }
    values = {field: value for field, value in overrides.items() if value is not None}
    if values:
        config = ScraperConfig(**{**config.__dict__, **values})
    config.validate()

    logger.info("CineScrapper version: %s", __version__)
    logger.info("Starting CineScrapper with config: %s", config)
    mongo_writer = create_mongo_writer(args.mongo_enabled, args.mongo_uri, args.mongo_db, args.mongo_collection)
    try:
        scrape_cinemas(args.wiki_source, args.year, mongo_writer, config)
    finally:
        if mongo_writer is not None:
            mongo_writer.close()
        logger.info("Ending CineScrapper...")


if __name__ == "__main__":
    main()
