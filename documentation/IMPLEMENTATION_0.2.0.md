# CineScrapper 0.2.0-dev overlay

This overlay adds controlled HTTP requests, retry/backoff, batch processing, and MongoDB-backed job/item progress to the existing CineScrapper repository. It does not replace the repository's existing parser or data models.

## Year range

Run one year (the default remains the current year):

```bash
cinescrapper --year 2024
```

Run an inclusive year range:

```bash
cinescrapper --start-year 2020 --end-year 2026
```

Resume after an interrupted run:

```bash
cinescrapper --start-year 2020 --end-year 2026 --resume
```

The scraper handles years in ascending order. A failure in one year is logged and does not prevent subsequent years in a range from being attempted. Invalid or incomplete year ranges are rejected by the CLI.

## Incremental MongoDB writes

For each processed film, `MongoCinemaWriter.save_cinema()` compares the scraped document fields against the matching existing document:

- `inserted`: no matching document exists; insert via upsert.
- `updated`: one or more scraped fields differ; update the scraped fields.
- `unchanged`: all scraped fields match; skip the database write.

MongoDB's `_id` and unrelated metadata are not used to decide whether the scraped data changed. The existing `upsert_cinema()` method remains available for compatibility. For reliable duplicate prevention across concurrent processes, create a unique index for the chosen stable identity (`ref`, or a normalized `(title, year)` fallback) after reviewing existing duplicates.

## Resume behaviour

When MongoDB is enabled, job and item status are stored in `scrape_jobs` and `scrape_items`. Re-running a year range normally re-scrapes its films and compares them with MongoDB, so changed source data can be detected. Use `--resume` after an interrupted run to skip items already marked completed. `--force` overrides `--resume` and reprocesses all items; MongoDB comparison still avoids unnecessary writes when data is identical.

Without MongoDB, the scraper can process a year range but does not have persistent job/item resume state.

## Docker Compose

Set `START_YEAR` and `END_YEAR` in the environment. Defaults are both `2026`, which runs a single year. Example:

```bash
START_YEAR=2020 END_YEAR=2026 docker compose --profile scraper run --rm scraper
```

## Notes

- The existing `--year` single-year option remains supported.
- The year range is inclusive.
- A scrape result is compared field-by-field only after Wikipedia/Apple Music processing succeeds.
- Verify MongoDB indexes and connection settings before production use.
