
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
    _tr : Tag
        The table row.
    Parse the row and extract header information, such as
    the column name and column span.
    """
    header_dict = {}
    h_cols = _tr.find_all("th")
    if h_cols:
        for th in h_cols:
            colspan = int(th.get("colspan", 1))
            header_dict[th.get_text(strip=True)] = colspan
    return header_dict


def sum_dict_field_values(_dict: dict, _key: str):
    """
    Get the sum of field values up to the specified key.
    Since indexing starts at zero, subtract one from the total.
    """
    total = 0
    for key, val in _dict.items():
        total += val
        if key == _key:
            break
    return total - 1


def clean_wiki_link(raw_href):
    """Clean a Wikipedia href if it contains a redundant host prefix."""
    if (
            raw_href
            and isinstance(raw_href, str)
            and raw_href.startswith("//en.wikipedia.org/")
    ):
        return raw_href[len("/en.wikipedia.org"):]
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
        case "Studio" | "Production" | "Producer":
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
        is_album_infobox = (
                "Soundtrack album" in table_text
                or "haudio" in table.get("class", [])
        )
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
            match = re.search(
                r"Soundtrack album\s+by\s+(.+)",
                _clean_text(description) or "",
                re.I,
                )
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


def parse_soundtrack_section(section_soup, cine_info: CineInfo = None):
    """
    Parse soundtrack information from a dedicated Music or Soundtrack section.
    Optionally update the supplied CineInfo object.
    """
    soundtrack = SoundtrackInfo()
    _parse_album_infobox(section_soup, soundtrack)

    section_text = section_soup.get_text(" ", strip=True)
    composer_match = re.search(
        r"(?:soundtrack(?: and film score)? is composed by|"
        r"score is composed by|composed by)\s+"
        r"(.*?)(?:\.|, marking|,|$)",
        section_text,
        re.I,
    )
    album_match = re.search(
        r"the soundtrack.*?(?:is featured in|for)\s+([A-Za-z0-9\s]+)",
        section_text,
        re.I,
    )

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
    Parse a Wikipedia track listing table and return TrackInfo objects.

    Expected columns commonly include:
    No | Title | Lyrics | Singers | Length
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

        if (
                "tracklist-total-length" in row.get("class", [])
                or "caption" in row.get("class", [])
        ):
            continue

        cols = row.find_all(["th", "td"])
        if len(cols) < 2:
            logger.warning("Skipping incomplete tracklist row.")
            continue

        try:
            track_info = TrackInfo()
            track_info.number = _parse_track_number(_clean_text(cols[0]))

            title_idx = header_map.get("title", 1)
            if title_idx < len(cols):
                track_info.title = _clean_text(cols[title_idx])

            lyrics_idx = header_map.get("lyrics")
            singers_idx = (
                    header_map.get("singers")
                    or header_map.get("artist")
                    or header_map.get("singer")
            )
            length_idx = header_map.get("length")

            if lyrics_idx is not None and lyrics_idx < len(cols):
                track_info.lyrics = _clean_text(cols[lyrics_idx])

            if singers_idx is not None and singers_idx < len(cols):
                track_info.singers = _clean_text(cols[singers_idx])

            if length_idx is not None and length_idx < len(cols):
                track_info.length = _clean_text(cols[length_idx])

            tracks.append(track_info)

        except Exception as exc:
            logger.error("Error parsing tracklist row: %s", exc)

    return tracks


def parse_soundtrack_page(soup: BeautifulSoup, cine_info: CineInfo = None):
    """Convert a movie page or soundtrack page into SoundtrackInfo."""
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
    Find a dedicated soundtrack page linked from a movie page, usually through
    a 'Main article: <film> (soundtrack)' hatnote in the Music/Soundtrack section.
    """
    for section in _soundtrack_sections(soup):
        for link in section.select(".hatnote a[href]"):
            title = link.get("title") or link.get_text(" ", strip=True)
            if "(soundtrack)" in title.lower():
                return clean_wiki_link(link.get("href"))

    return None


def _table_grid_rows(table):
    """
    Expand table rows into logical columns while respecting rowspan and colspan.

    A cell with rowspan occupies the same logical column in subsequent rows.
    A cell with colspan occupies multiple logical columns.
    """
    grid = []
    active = {}

    for tr in table.find_all("tr"):
        row = []
        next_active = {}
        col = 0

        cells = tr.find_all(["th", "td"], recursive=False)

        for cell in cells:
            # Fill columns occupied by cells carried over from prior rows.
            while col in active:
                remaining, span_cell = active[col]
                row.append(span_cell)

                if remaining > 1:
                    next_active[col] = (remaining - 1, span_cell)

                col += 1

            colspan = max(1, int(cell.get("colspan", 1) or 1))
            rowspan = max(1, int(cell.get("rowspan", 1) or 1))

            for offset in range(colspan):
                target = col + offset

                while len(row) <= target:
                    row.append(None)

                row[target] = cell

                if rowspan > 1:
                    next_active[target] = (rowspan - 1, cell)

            col += colspan

        # Preserve any rowspan columns not consumed by a new cell.
        if active:
            for active_col, (remaining, span_cell) in active.items():
                if active_col in next_active:
                    continue

                while len(row) <= active_col:
                    row.append(None)

                if row[active_col] is None:
                    row[active_col] = span_cell

                if remaining > 1:
                    next_active[active_col] = (remaining - 1, span_cell)

        grid.append(row)
        active = next_active

    return grid


def _table_header_name(cell):
    if cell is None:
        return ""
    return _normalise_header(_clean_text(cell) or "")


def parse_table(_table, _year):
    """
    Parse films from a Wikipedia yearly film-list table.

    The parser distinguishes real column headers from month separator rows
    such as JULY and AUGUST. It also accounts for rowspan and colspan so that
    film details remain aligned with the correct columns.
    """
    cinemas = []
    header_map = None
    grid_rows = _table_grid_rows(_table)

    aliases = {
        "title": "title",
        "film": "title",
        "director": "director",
        "cast": "cast",
        "starring": "cast",
        "studio": "studio",
        "productioncompany": "studio",
        "production": "studio",
        "producer": "producer",
        "ref": "ref",
        "references": "ref",
    }

    month_names = {
        "january", "february", "march", "april", "may", "june",
        "july", "august", "september", "october", "november", "december",
    }

    for row in grid_rows:
        if not row:
            continue

        # Detect an actual header row by its column labels.
        candidate = {}

        for col_idx, cell in enumerate(row):
            if cell is None or cell.name != "th":
                continue

            normalized = _table_header_name(cell)
            field = aliases.get(normalized)

            if field and field not in candidate:
                candidate[field] = col_idx

        # A month separator has a single <th> such as JULY. It must not
        # overwrite the existing film-table header mapping.
        if "title" in candidate and len(candidate) >= 2:
            header_map = candidate
            logger.debug("Detected film table headers: %s", header_map)
            continue

        data_cells = [
            cell for cell in row
            if cell is not None and cell.name == "td"
        ]

        if not data_cells or not header_map:
            continue

        title_idx = header_map["title"]

        if title_idx >= len(row):
            logger.warning(
                "Skipping row with no title column at expected index %s",
                title_idx,
            )
            continue

        title_cell = row[title_idx]
        title_text = _clean_text(title_cell)

        if not title_text:
            continue

        if _normalise_header(title_text) in (
                {"title", "film"} | month_names
        ):
            continue

        cinema = CineInfo()
        cinema.year = _year
        cinema.title = title_text

        title_link = title_cell.find("a", href=True)
        if title_link:
            cinema.ref = clean_wiki_link(title_link.get("href"))

        for field, attr in (
                ("director", "director"),
                ("cast", "cast"),
                ("studio", "studio"),
                ("producer", "studio"),
        ):
            col_idx = header_map.get(field)

            if col_idx is None or col_idx >= len(row):
                continue

            cell = row[col_idx]
            value = _clean_text(cell)

            if not value:
                continue

            if field == "cast":
                # Preserve the existing model convention:
                # cast is a semicolon-separated list.
                value = re.sub(r"\s*,\s*", ";", value)
                setattr(cinema, attr, value.split(";"))
            else:
                setattr(cinema, attr, value)

        cinemas.append(cinema)

    logger.debug("Parsed %d cinema rows for year %s", len(cinemas), _year)
    return cinemas
