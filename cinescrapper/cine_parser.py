import re
from cinescrapper import cine_helper
from cinescrapper.logger import get_logger
from cinescrapper.cine_model import CineInfo, TrackInfo # Import TrackInfo

logger = get_logger()


def parse_header_dict(_tr):
    """
    Parameters
        ----------
        _tr : Canvas
            The table row as Canvas
    Parse the row, extract the header information
    such as name and column span as a dictionary
    """
    header_dict = {}
    h_cols = _tr.find_all("th")
    if len(h_cols) > 0:
        for th in h_cols:
            colspan = int(th.get("colspan", 1))
            header_dict[th.get_text(strip=True)] = colspan
    return header_dict


def sum_dict_field_values(_dict: dict, _key: str):
    """
    Get the sum of the field values till the key input.
    Since the index starts from 0, subtract the total with -1.
    :param _dict:
    :param _key:
    :return:
    """
    total = 0
    for key, val in _dict.items():
        total = total + val
        if key == _key:
            break
    return total - 1

def clean_wiki_link(raw_href):
    """
    Cleans a Wikipedia raw href by removing the redundant '//en.wikipedia.org/' prefix if present.
    """
    if raw_href and isinstance(raw_href, str) and raw_href.startswith("//en.wikipedia.org/"):
        return raw_href[len("/en.wikipedia.org/"):]
    return raw_href


def map_cinema(_cinema, _header, _value):
    match _header:
        case "Title":
            val_arr = _value.split("****") if _value else [_value]
            if len(val_arr) > 1:
                _cinema.title = val_arr[0]
                _cinema.ref = clean_wiki_link(val_arr[1])
            else:
                _cinema.title = _value
        case "Director":
            _cinema.director = _value
        case "Cast":
            _cinema.cast = _value.split(";") if _value is not None else []
        case "Studio":
            _cinema.studio = _value
        case "Production":
            _cinema.studio = _value
        case "Producer":
            _cinema.studio = _value


def parse_soundtrack_section(section_soup: BeautifulSoup, cine_info: CineInfo):
    """
    Parses soundtrack information from a dedicated section (e.g., 'Soundtrack').
    Updates the provided CineInfo object with extracted details.
    """
    # Look for common phrases indicating composer and album/soundtrack info
    composer_match = re.search(r'(?:composed by|score is composed by)\s+(.*?)(?:\s+and|\.|$)', section_soup.get_text())
    album_match = re.search(r'the soundtrack.*?(?:is featured in|for)\s+([A-Za-z0-9\s]+)', section_soup.get_text(), re.IGNORECASE)

    if composer_match:
        composer = composer_match.group(1).strip()
        cine_info.composer = composer
        logger.debug("Extracted Composer from soundtrack section: %s", composer)

    if album_match:
        album = album_match.group(1).strip()
        cine_info.album_name = album
        logger.debug("Extracted Album Name from soundtrack section: %s", album)


def parse_tracklist(table):
    """
    Parses a Wikipedia track listing table (class 'tracklist') and extracts TrackInfo objects.
    Assumes the structure: No | Title | Lyrics | Singer(s) | Length
    Returns a list of TrackInfo objects.
    """
    tracks = []
    tbody = table.find("tbody")
    if not tbody:
        logger.warning("Tracklist table found but no <tbody> tag.")
        return tracks

    rows = tbody.find_all("tr")
    for row in rows:
        # Skip header and total length rows
        if "tracklist-total-length" in row.get("class", "") or "caption" in row.get("class", ""):
            continue

        cols = row.find_all(['th', 'td'])
        if len(cols) < 5:
            logger.warning("Skipping incomplete tracklist row.")
            continue

        # Extract data based on expected column order (No, Title, Lyrics, Singer(s), Length)
        try:
            track_info = TrackInfo()
            
            # Column 1: Number (th scope="row")
            number = cols[0].get_text(strip=True)
            if number and number.isdigit():
                pass # We don't store the number, but we check if it's a valid row start

            # Column 2: Title
            title_element = cols[1]
            track_info.title = title_element.get_text(strip=True)

            # Column 3: Lyrics
            lyrics_element = cols[2]
            track_info.lyrics = lyrics_element.get_text(strip=True)

            # Column 4: Singer(s)
            singers_element = cols[3]
            track_info.singers = singers_element.get_text(strip=True)

            # Column 5: Length
            length_element = cols[4]
            track_info.length = length_element.get_text(strip=True)

            tracks.append(track_info)
        except Exception as e:
            logger.error("Error parsing tracklist row: %s", e)
            continue
    return tracks


def parse_table(_table, _year):
    cinemas = []
    tr_tag = _table.find_all("tr")
    tr_len = len(tr_tag)
    logger.debug("Available rows to parse > %s", tr_len)

    header_count = 0
    header_dict = {}
    idx_title = -1
    for idx_tr in range(tr_len):
        tr = tr_tag[idx_tr]
        temp_headers_dict = parse_header_dict(tr)
        if len(temp_headers_dict) > 0:
            header_dict = temp_headers_dict
            header_count = cine_helper.sum_dict_values(header_dict)
            idx_title = sum_dict_field_values(header_dict, "Title")
            logger.debug("Available Headers > %s", header_dict)
            logger.debug("Available Header Count > %d", header_count)
        else:
            td_tag = tr.find_all("td")
            td_len = len(td_tag)
            diff = header_count - td_len
            entity = []

            # If the Size doesn't match with the total header count,
            # add blank as filler (due to different colspan).
            if diff > 0:
                for i_filler in range(diff):
                    entity.append("")

            for idx_td in range(td_len):
                td = td_tag[idx_td]
                td_value = td.get_text(strip=True)

                a = td.find("a")
                href = a.get("href") if a else None
                if idx_td == (idx_title - diff) and href is not None:
                    td_value = td_value + "****" + href
                td_value = td_value.replace(", ", ";")
                td_value = td_value.replace(",", ";")

                entity.append(re.sub(r"\s+", " ", str(td_value)).strip())

            idx_row = 0
            cine_info = CineInfo()
            cine_info.year = _year
            if len(header_dict) == header_count:
                for head in header_dict.keys():
                    value = entity[idx_row]
                    map_cinema(cine_info, head, value)
                    idx_row += 1
            else:
                for header, colspan_header in header_dict.items():
                    value = ""
                    if colspan_header > 1:
                        for idx_colspan in range(colspan_header):
                            value = value + " " + entity[idx_colspan + idx_row]
                        idx_row += colspan_header - 1
                    else:
                        if idx_row == 0:
                            value = entity[idx_row]
                        else:
                            value = entity[colspan_header + idx_row]
                        idx_row += colspan_header
                    map_cinema(cine_info, header, value)

            cinemas.append(cine_info)
    return cinemas
