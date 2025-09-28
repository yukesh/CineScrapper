from datetime import date

from cinescrapper import __version__
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

    args = parser.parse_args()

    setup_logger(args.log_level)
    logger = get_logger()

    logger.info(f"CineScrapper version: {__version__}")
    logger.info("Starting CineScrapper...")
    logger.info(f"Arguments: {args}")

    # Entry point for processing cinemas
    scrape_cinemas(args.wiki_source, args.year)
    logger.info("Ending CineScrapper...")


main()
