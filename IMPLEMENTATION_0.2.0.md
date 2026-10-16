# CineScrapper 0.2.0-dev implementation overlay

This overlay refactors the scraper into a restartable batch pipeline without changing the existing parser/model contract.

## Flow

```text
CLI
  -> discover yearly movie rows
  -> BatchProcessor
       -> MovieProcessor
            -> Wikipedia (cached + rate limited + retry)
            -> Apple/iTunes (rate limited + retry)
       -> Mongo movie upsert
       -> Mongo scrape item state
```

## Batch behaviour

- `--batch-size` controls the number of movies handled per batch.
- A movie is marked `COMPLETED` only after movie processing and Mongo upsert succeed.
- A failed movie is marked `FAILED`; processing continues with the rest of the batch.
- The job ends with a non-zero exception when any movie failed, allowing Docker/cron to detect a partial failure.
- A subsequent run skips completed items for the same `wiki-source/year/v0.2.0` job unless `--force` is used.

## Mongo collections

Existing movie data remains in the configured cinema collection.

Two additional collections are created when Mongo is enabled:

- `scrape_jobs`: one document per logical scrape job.
- `scrape_items`: per-movie completion/failure state.

## Rate limits

Defaults:

- Wikipedia: 1.5 seconds minimum interval + jitter
- Apple/iTunes: 2.0 seconds minimum interval + jitter
- retries: 3 attempts
- retry delay honours `Retry-After` for 429 responses and uses bounded exponential backoff otherwise

CLI values override environment values.

## Docker

The container is intentionally a finite job. Starting the scraper container performs one scrape job and then exits.

Example:

```bash
YEAR=2026 BATCH_SIZE=10 docker compose --profile scraper run --rm scraper
```

Force a complete reprocessing of the job:

```bash
docker compose --profile scraper run --rm scraper --force
```

## Important

This is an overlay against the `0.1.1-dev` branch. It does not push or modify GitHub. Apply the files locally, run the test suite, then commit when you are happy with the behaviour.
