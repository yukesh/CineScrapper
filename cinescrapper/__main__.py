
from datetime import date
import argparse

from cinescrapper import __version__
from cinescrapper.config import ScraperConfig
from cinescrapper.env import mongo_settings, mongo_uri_profiles
from cinescrapper.mongo_writer import create_mongo_writer
from cinescrapper.scrapper import scrape_cinemas
from cinescrapper.logger import setup_logger, get_logger


def main():
    parser = argparse.ArgumentParser(description="CineScrapper: Scrape cinema data from Wikipedia.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
    parser.add_argument("--language", default="thamizh", choices=("thamizh", "hindi", "telugu", "malayalam", "kannada"), help="Language collection to scrape")
    parser.add_argument("--wiki-source", help="Override the Wikipedia master page for the selected language")
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
    profiles = mongo_uri_profiles()
    parser.add_argument("--mongo-uri-profile", choices=sorted(profiles), help="Named URI profile configured in cinescrapper.properties")
    parser.add_argument("--mongo-uri", help="MongoDB connection URI (overrides the selected profile)")
    parser.add_argument("--mongo-db", help="MongoDB database name")
    parser.add_argument("--mongo-collection", help="Override the default language collection")
    args = parser.parse_args()

    if (args.start_year is None) != (args.end_year is None):
        parser.error("--start-year and --end-year must be supplied together")
    if args.start_year is not None and args.start_year > args.end_year:
        parser.error("--start-year must be less than or equal to --end-year")
    if args.year is not None and args.start_year is not None:
        parser.error("Use either --year or --start-year/--end-year, not both")

    setup_logger(args.log_level)
    logger = get_logger()
    config = ScraperConfig.from_properties()
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
    wiki_sources = {
        "thamizh": "Lists_of_Tamil-language_films",
        "hindi": "Lists_of_Hindi-language_films",
        "telugu": "Lists_of_Telugu-language_films",
        "malayalam": "Lists_of_Malayalam-language_films",
        "kannada": "Lists_of_Kannada-language_films",
    }
    wiki_source = args.wiki_source or wiki_sources[args.language]
    mongo = mongo_settings(args.mongo_uri_profile)
    mongo_uri = args.mongo_uri or mongo["uri"]
    database_name = args.mongo_db or mongo["database"]
    collection_name = args.mongo_collection or args.language
    if args.mongo_enabled:
        missing = [name for name, value in (("MongoDB URI", mongo_uri), ("MongoDB database", database_name)) if not value]
        if missing:
            parser.error(
                "MongoDB is enabled but required settings are missing: "
                + ", ".join(missing)
                + ". Set a configured URI environment variable and [mongodb] database."
            )
    mongo_writer = create_mongo_writer(args.mongo_enabled, mongo_uri or "", database_name or "", collection_name)
    try:
        if args.start_year is not None:
            scrape_cinemas(
                wiki_source,
                args.start_year,
                mongo_writer,
                config,
                end_year=args.end_year,
            )
        else:
            scrape_cinemas(wiki_source, args.year or date.today().year, mongo_writer, config)
    finally:
        if mongo_writer is not None:
            mongo_writer.close()
        logger.info("Ending CineScrapper...")


if __name__ == "__main__":
    main()
