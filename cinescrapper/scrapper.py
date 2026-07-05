import re
from cinescrapper import cine_helper, apple_music_client
from cinescrapper import cine_parser
from cinescrapper import cine_constants
from cinescrapper.logger import get_logger
from cinescrapper.wiki_client import WikiClient
from cinescrapper.cine_model import SourceInfo

logger = get_logger()


def clean_wiki_link(raw_href):
    """
    Cleans a Wikipedia raw href by removing the redundant '//en.wikipedia.org/' prefix if present.
    """
    if raw_href and isinstance(raw_href, str) and raw_href.startswith("//en.wikipedia.org/"):
        return raw_href[len("/en.wikipedia.org/"):]
    return raw_href


def get_soundtrack_page_name(raw_href):
    """
    Cleans a Wikipedia raw href by removing the redundant '/wiki/' prefix if present.
    """
    if raw_href and isinstance(raw_href, str) and raw_href.startswith("/wiki/"):
        return raw_href[len("/wiki/"):]
    return raw_href


def find_cinemas(_master_wiki_page: str, _start_year: int, _end_year: int = None, _condition: str = None):
    """
    Find cinema wiki links based on year and condition.
    Args:
        _master_wiki_page: The master wiki page containing the list of Tamil-language films.
        _start_year (int): The starting year for filtering.
        _end_year (int, optional): The ending year for filtering (exclusive).
        _condition (str, optional): 'gtr' for greater than _start_year, 'ltr' for less than _start_year, or None for exact match.
    Returns:
        dict: Mapping of cinema titles to their wiki hrefs.
    """
    client = WikiClient()

    # Fetch the soup object for the master wiki page
    soup = client.fetch_soup("/wiki/" + _master_wiki_page, _master_wiki_page)
    div_tag = soup.find("div", {"id": "mw-content-text"}) if soup is not None else None

    cinemas = {}
    if div_tag is not None:
        # Find all anchor tags with titles matching 'List of Tamil films'
        a_tag = div_tag.find_all("a", title=re.compile("List of Tamil films", re.I))
        for a in a_tag:
            title = a.get("title")
            year = int(cine_helper.find_year(title))
            # Filter based on the provided condition
            if ((_condition == "gtr" and year > _start_year)
                    or (_condition == "ltr" and year < _start_year)):
                raw_href = a.get("href")
                href = clean_wiki_link(raw_href)
                cinemas[title] = href
            elif _start_year is not None and _end_year is not None:
                if _start_year < year < _end_year:
                    raw_href = a.get("href")
                    href = clean_wiki_link(raw_href)
                    cinemas[title] = href
            elif _condition is None:
                if year == _start_year:
                    raw_href = a.get("href")
                    href = clean_wiki_link(raw_href)
                    cinemas[title] = href
                    break
    else:
        logger.info("No Div Tag Found for Cinemas")
    return cinemas


def find_cinema(_master_wiki_page, _year):
    """
    Find cinema wiki links for a specific year.
    """
    return find_cinemas(_master_wiki_page, _year)


def find_cinemas_greater(_master_wiki_page, _year):
    """
    Find cinema wiki links for years greater than the given year.
    """
    return find_cinemas(_master_wiki_page, _year, None, "gtr")


def find_cinemas_lesser(_master_wiki_page, _year):
    """
    Find cinema wiki links for years less than the given year.
    """
    return find_cinemas(_master_wiki_page, _year, None, "ltr")


def scrape_cinemas(_master_wiki_page: str, _year: int):
    """
    Process cinemas for the requested year, parse tables, and log information about movies and their soundtracks.
    """
    cinemas = find_cinema(_master_wiki_page, _year)
    client = WikiClient() if len(cinemas) > 0 else None
    for title, ref_link in cinemas.items():
        logger.debug("Title [%s] and link is %s", title, ref_link)
        soup = client.fetch_soup(ref_link, title)
        all_wikitables = soup.find_all("table", {"class": "wikitable"})
        year = int(cine_helper.find_year(title))

        wiki_len = len(all_wikitables)
        total_count = 0
        track_count = 0
        for idx_table in range(wiki_len):
            if idx_table != -1:
                wikitable = all_wikitables[idx_table]
                # Parse the wikitable for cinema rows
                cinema_rows = cine_parser.parse_table(wikitable, year)

                cinemas_len = len(cinema_rows)
                logger.debug("Total cinemas in the wiki table are %d", cinemas_len)
                total_count += cinemas_len

                for idx_cinema in range(cinemas_len):
                    logger.debug("Currently parsing %d out of %d", idx_cinema + 1, cinemas_len)
                    cinema = cinema_rows[idx_cinema]
                    if cinema.title is not None:
                        # --- Soundtrack Parsing (Inline Content) ---
                        # Find all sections that might contain soundtrack info
                        sections = soup.find_all("section", {"data-mw-section-id": "3"}) # Targeting section ID 3 as per example
                        for section in sections:
                            cine_parser.parse_soundtrack_section(section, cinema)

                        # --- Tracklist Parsing (Structured Table Content) ---
                        tracklist_tables = soup.find_all("table", {"class": "tracklist"})
                        for track_table in tracklist_tables:
                            tracks = cine_parser.parse_tracklist(track_table)
                            for track in tracks:
                                cinema.add_track(track)

                        # --- Apple Music Lookup ---
                        result = apple_music_client.get_apple_music_album_url(cinema.title, year)
                        if result is not None:
                            logger.info("Found Apple Music Album: %s by %s",
                                        result.get("albumName"),
                                        result.get("artistName"))
                            source_info = SourceInfo("Apple Music", result.get("appleMusicUrl"))
                            cinema.add_source(source_info)
                        else:
                            logger.warning("No Apple Music Album found for: %s", cinema.title)
                        logger.debug("Cinema Node: %s", cinema.to_dict())

                        # --- Soundtrack Link Processing (Separate Page) ---
                        if cinema.ref is not None and len(cinema.ref) > 0:
                            cinema_ref_link = cinema.ref
                            logger.debug("Cinema Ref Linke %s ", cinema_ref_link)
                            soup = client.fetch_soup(cinema.ref, get_soundtrack_page_name(cinema.ref), cine_constants.TYPE_MOVIE)
                            # load_sound_track(album)


                            track_count += 1
                            if track_count > 10:
                                break
                        else:
                            # logger.warning("Link not available to get soundtrack info")
                            tc1 = 1

                    else:
                        logger.warning("Title is not available for the index %d", idx_cinema)
                    # publish_mongo(album, collection)
        logger.info("Total # Cinemas are %d", total_count)
        logger.info("Total # Cinemas with Soundtrack links are %d", track_count)
