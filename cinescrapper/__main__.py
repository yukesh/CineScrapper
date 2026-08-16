from datetime import date

from cinescrapper import __version__
from cinescrapper.mongo_writer import create_mongo_writer
from cinescrapper.scrapper import scrape_cinemas
from cinescrapper.logger import setup_logger, get_logger
import argparse


def main():
    parser = argparse.ArgumentParser(description="CineScrapper: Scrape cinema data from Wikipedia.")

    parser.add_argument(
        "--log-level", type=str, default="DEBUG",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Set logging level"
    )

    parser.add_argument(
        '--wiki-source',
        type=str,
        default="Lists_of_Tamil-language_films",
        help='Wikipedia master page to scrape (default: Lists_of_Tamil-language_films)'
    )

    parser.add_argument(
        '--year',
        type=int,
        default=date.today().year,
        help='Year of the films to scrape (default: current year)'
    )

    parser.add_argument(
        "--mongo-enabled",
        action="store_true",
        help="Write scraped cinema data to MongoDB"
    )

    parser.add_argument(
        "--mongo-uri",
        type=str,
        default="mongodb://localhost:27017",
        help="MongoDB connection string"
    )

    parser.add_argument(
        "--mongo-db",
        type=str,
        default="cinescrapper",
        help="MongoDB database name"
    )

    parser.add_argument(
        "--mongo-collection",
        type=str,
        default="cinemas",
        help="MongoDB collection name"
    )

    args = parser.parse_args()

    setup_logger(args.log_level)
    logger = get_logger()

    logger.info(f"CineScrapper version: {__version__}")
    logger.info("Starting CineScrapper...")
    logger.info(f"Arguments: {args}")

    mongo_writer = create_mongo_writer(
        args.mongo_enabled,
        args.mongo_uri,
        args.mongo_db,
        args.mongo_collection,
    )
    try:
        # Entry point for processing cinemas
        scrape_cinemas(args.wiki_source, args.year, mongo_writer)
    finally:
        if mongo_writer is not None:
            mongo_writer.close()
        logger.info("Ending CineScrapper...")


if __name__ == "__main__":
    main()
