# Command reference

## Scrape movies

```sh
cinescrapper --language thamizh --year 2026 --mongo-enabled
cinescrapper --language hindi --start-year 2020 --end-year 2023 --mongo-enabled
```

The supported lowercase language values are `thamizh`, `hindi`, `telugu`, `malayalam`, and `kannada`. The language selects both the Wikipedia source and, by default, a same-named MongoDB collection (`--language hindi` writes to `hindi`). `--wiki-source` overrides the source page; `--mongo-collection` overrides the collection. MongoDB settings come from `cinescrapper.properties` and its selected environment-variable URI profile unless overridden with `--mongo-uri` and `--mongo-db`.

## Common options

- `--year YEAR`: scrape one year (defaults to the current year).
- `--start-year YEAR --end-year YEAR`: scrape an inclusive range.
- `--mongo-enabled`: persist results. Without this flag, MongoDB is not used.
- `--mongo-uri-profile NAME`: choose a named profile from `[mongodb.uris]`, such as `cloud` or `mylocal`.
- `--batch-size N`: records per batch.
- `--resume`: skip movies already marked complete in job state.
- `--force`: reprocess all discovered movies.
- `--log-level LEVEL`: `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`.
- `--wiki-rate-limit SECONDS`, `--apple-music-rate-limit SECONDS`: minimum request spacing.
- `--max-retries N`, `--retry-base-delay SECONDS`, `--retry-max-delay SECONDS`: retry policy.
- `--cache-ttl SECONDS`, `--request-timeout SECONDS`: cache and network timing.

Run `cinescrapper --help` for the complete current option list. For MongoDB utilities and operational procedures, see the [documentation index](README.md).

## Copy tracks selected for a collection

Preview selected audio and matching LRC files before copying:

```sh
python -m cinescrapper.copy_collection_tracks \
  --source-root "/your/music/root/Thamizh" \
  --target-folder "/your/collection"
```

Add `--apply` after reviewing the preview. Settings come from `cinescrapper.properties` and the selected environment-variable URI profile. See the [collection copy workflow](COLLECTION_COPY_WORKFLOW.md) for the output layout and overwrite behavior.
