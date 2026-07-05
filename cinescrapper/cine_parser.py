import re
from bs4 import BeautifulSoup
from cinescrapper import cine_helper
from cinescrapper.logger import get_logger
from cinescrapper.cine_model import CineInfo, SoundtrackInfo, TrackInfo

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


def _clean_text(element):
    if element is None:
        return None
    text = element.get_text(" ", strip=True)
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip('"')
    return text or None


def _normalise_header(header):
    return re.sub(r"[^a-z0-9]+", "", header.lower())


def _parse_track_number(value):
    if not value:
        return None
    match = re.search(r"\d+", value)
    return int(match.group()) if match else None


def _parse_album_infobox(soup: BeautifulSoup, soundtrack: SoundtrackInfo):
    for table in soup.find_all("table", {"class": "infobox"}):
        table_text = table.get_text(" ", strip=True)
        is_album_infobox = "Soundtrack album" in table_text or "haudio" in table.get("class", [])
        if not is_album_infobox:
            continue

        album = table.select_one(".summary.album")
        contributor = table.select_one(".contributor")
        description = table.select_one(".description")

        if album and not soundtrack.album_name:
            soundtrack.album_name = _clean_text(album)
        if contributor and not soundtrack.composer:
            soundtrack.composer = _clean_text(contributor)
        elif description and not soundtrack.composer:
            match = re.search(r"Soundtrack album\s+by\s+(.+)", _clean_text(description) or "", re.I)
            if match:
                soundtrack.composer = match.group(1).strip()


def _parse_film_infobox_music(soup: BeautifulSoup, soundtrack: SoundtrackInfo):
    if soundtrack.composer:
        return
    for row in soup.select("table.infobox tr"):
        label = row.find("th", {"class": "infobox-label"})
        data = row.find("td", {"class": "infobox-data"})
        if label and data and _clean_text(label) == "Music by":
            soundtrack.composer = _clean_text(data)
            return


def _soundtrack_sections(soup: BeautifulSoup):
    sections = []
    for section in soup.find_all("section"):
        heading = section.get("aria-labelledby") or ""
        if heading.lower() in {"music", "soundtrack"}:
            sections.append(section)
    return sections


def parse_soundtrack_section(section_soup: BeautifulSoup, cine_info: CineInfo = None):
    """
    Parses soundtrack information from a dedicated section (e.g., 'Soundtrack').
    Optionally updates the provided CineInfo object with extracted details.
    """
    soundtrack = SoundtrackInfo()
    _parse_album_infobox(section_soup, soundtrack)

    section_text = section_soup.get_text(" ", strip=True)
    composer_match = re.search(
        r"(?:soundtrack(?: and film score)? is composed by|score is composed by|composed by)\s+(.*?)(?:\.|, marking|,|$)",
        section_text,
        re.I,
    )
    album_match = re.search(r"the soundtrack.*?(?:is featured in|for)\s+([A-Za-z0-9\s]+)", section_text, re.I)

    if composer_match and not soundtrack.composer:
        soundtrack.composer = composer_match.group(1).strip()
    if album_match:
        soundtrack.album_name = album_match.group(1).strip()

    for track_table in section_soup.find_all("table", {"class": "tracklist"}):
        for track in parse_tracklist(track_table):
            soundtrack.add_track(track)

    if cine_info is not None:
        cine_info.apply_soundtrack(soundtrack)
    return soundtrack


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
    header_map = {}
    for row in rows:
        header_cells = row.find_all("th", scope="col")
        if header_cells:
            for idx, cell in enumerate(header_cells):
                header = _normalise_header(_clean_text(cell) or "")
                header_map[header] = idx
            continue

        # Skip header and total length rows
        if "tracklist-total-length" in row.get("class", []) or "caption" in row.get("class", []):
            continue

        cols = row.find_all(['th', 'td'])
        if len(cols) < 2:
            logger.warning("Skipping incomplete tracklist row.")
            continue

        try:
            track_info = TrackInfo()

            track_info.number = _parse_track_number(_clean_text(cols[0]))
            track_info.title = _clean_text(cols[header_map.get("title", 1)])

            lyrics_idx = header_map.get("lyrics")
            singers_idx = header_map.get("singers") or header_map.get("artist") or header_map.get("singer")
            length_idx = header_map.get("length")

            if lyrics_idx is not None and lyrics_idx < len(cols):
                track_info.lyrics = _clean_text(cols[lyrics_idx])
            if singers_idx is not None and singers_idx < len(cols):
                track_info.singers = _clean_text(cols[singers_idx])
            if length_idx is not None and length_idx < len(cols):
                track_info.length = _clean_text(cols[length_idx])

            tracks.append(track_info)
        except Exception as e:
            logger.error("Error parsing tracklist row: %s", e)
            continue
    return tracks


def parse_soundtrack_page(soup: BeautifulSoup, cine_info: CineInfo = None):
    """
    Converts a movie page or a dedicated soundtrack page into SoundtrackInfo.
    """
    soundtrack = SoundtrackInfo()
    _parse_album_infobox(soup, soundtrack)
    _parse_film_infobox_music(soup, soundtrack)

    sections = _soundtrack_sections(soup)
    parse_roots = sections if sections else [soup]
    for root in parse_roots:
        section_soundtrack = parse_soundtrack_section(root)
        if section_soundtrack.album_name and not soundtrack.album_name:
            soundtrack.album_name = section_soundtrack.album_name
        if section_soundtrack.composer and not soundtrack.composer:
            soundtrack.composer = section_soundtrack.composer
        for track in section_soundtrack.tracks:
            soundtrack.add_track(track)

    if cine_info is not None:
        cine_info.apply_soundtrack(soundtrack)
    return soundtrack


def find_soundtrack_page_link(soup: BeautifulSoup):
    """
    Finds a dedicated soundtrack page linked from a movie page, usually through
    a 'Main article: <film> (soundtrack)' hatnote in the Music/Soundtrack section.
    """
    for section in _soundtrack_sections(soup):
        for link in section.select(".hatnote a[href]"):
            title = link.get("title") or link.get_text(" ", strip=True)
            if "(soundtrack)" in title.lower():
                return clean_wiki_link(link.get("href"))
    return None


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
