
from cinescrapper.env import load_project_env

load_project_env()

from datetime import date
import argparse
import os

from cinescrapper import __version__
from cinescrapper.config import ScraperConfig
from cinescrapper.mongo_writer import create_mongo_writer
from cinescrapper.scrapper import scrape_cinemas
from cinescrapper.logger import setup_logger, get_logger


def main():
    parser = argparse.ArgumentParser(description="CineScrapper: Scrape cinema data from Wikipedia.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--wiki-source", default="Lists_of_Tamil-language_films")
    year_group = parser.add_mutually_exclusive_group()
    year_group.add_argument("--year", type=int, help="Scrape a single year (defaults to the current year)")
    parser.add_argument("--start-year", type=int, help="First year in an inclusive year range")
    parser.add_argument("--end-year", type=int, help="Last year in an inclusive year range")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--wiki-rate-limit", type=float, default=None, help="Minimum seconds between Wikipedia requests")
    parser.add_argument("--apple-music-rate-limit", type=float, default=None, help="Minimum seconds between Apple/iTunes requests")
    parser.add_argument("--rate-limit-jitter", type=float, default=None)
    parser.add_argument("--max-retries", type=int, default=None)
    parser.add_argument("--retry-base-delay", type=float, default=None)
    parser.add_argument("--retry-max-delay", type=float, default=None)
    parser.add_argument("--cache-ttl", type=int, default=None, help="Wikipedia cache TTL in seconds")
    parser.add_argument("--request-timeout", type=float, default=None)
    parser.add_argument("--resume", action="store_true", help="Skip movies already completed in the saved job state")
    parser.add_argument("--force", action="store_true", help="Reprocess all movies; overrides --resume")
    parser.add_argument("--mongo-enabled", action="store_true")
    parser.add_argument(
        "--mongo-uri",
        default=os.getenv(
            "CINESCRAPPER_MONGO_URI",
            os.getenv("MONGODB_URI", "mongodb://localhost:27017"),
        ),
        help="MongoDB connection URI",
    )
    parser.add_argument(
        "--mongo-db",
        default=os.getenv(
            "CINESCRAPPER_MONGODB_DATABASE",
            os.getenv("MONGODB_DATABASE", "cinescrapper"),
        ),
        help="MongoDB Database Name",
    )
    parser.add_argument(
        "--mongo-collection",
        default=os.getenv(
            "CINESCRAPPER_MONGODB_COLLECTION",
            os.getenv("MONGODB_COLLECTION", "cinemas"),
        ),
        help="MongoDB Collection Name",
    )
    args = parser.parse_args()

    if (args.start_year is None) != (args.end_year is None):
        parser.error("--start-year and --end-year must be supplied together")
    if args.start_year is not None and args.start_year > args.end_year:
        parser.error("--start-year must be less than or equal to --end-year")
    if args.year is not None and args.start_year is not None:
        parser.error("Use either --year or --start-year/--end-year, not both")

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
        "resume": True if args.resume else None,
    }
    values = {field: value for field, value in overrides.items() if value is not None}
    if values:
        config = ScraperConfig(**{**config.__dict__, **values})
    config.validate()

    logger.info("CineScrapper version: %s", __version__)
    logger.info("Starting CineScrapper with config: %s", config)
    mongo_writer = create_mongo_writer(args.mongo_enabled, args.mongo_uri, args.mongo_db, args.mongo_collection)
    try:
        if args.start_year is not None:
            scrape_cinemas(
                args.wiki_source,
                args.start_year,
                mongo_writer,
                config,
                end_year=args.end_year,
            )
        else:
            scrape_cinemas(args.wiki_source, args.year or date.today().year, mongo_writer, config)
    finally:
        if mongo_writer is not None:
            mongo_writer.close()
        logger.info("Ending CineScrapper...")


if __name__ == "__main__":
    main()
