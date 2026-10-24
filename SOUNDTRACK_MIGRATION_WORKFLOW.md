# Soundtrack field migration and local-library workflow

This update separates Wikipedia-scraped soundtrack metadata from local audio files.

- `soundtrack_wiki`: Wikipedia/film-page soundtrack metadata, including album, composer and scraped track listing.
- `soundtrack`: local-library tracks only. Each track has exactly `fileName`, `relative_path`, and `add_collection`.
- New local tracks default to `add_collection: false`.
- The local reconciliation script does not set or change cinema-level `downloaded`.
- Future Wikipedia scrapes write `soundtrack_wiki`; they do not replace `soundtrack`.

## Important order

1. Stop any running scraper.
2. Update the project files from this ZIP.
3. Run the migration in dry-run mode and inspect the conflicts.
4. Apply the migration.
5. Only after the migration, run the updated Wikipedia scraper when needed.
6. Scan local folders and run local soundtrack reconciliation in dry-run mode.
7. Apply reconciliation after reviewing reports.
8. Export any local cinema folders not represented in MongoDB; review possible title matches and approve only genuinely distinct multilingual/otherwise-missing cinema records.

Do not run the old scraper against MongoDB before step 4. If a document already has both `soundtrack` and `soundtrack_wiki`, the migration intentionally leaves it unchanged and reports it for manual review instead of overwriting either field.

## 1. Migrate the existing field

From the project root:

```bash
source venv/bin/activate

python -m cinescrapper.migrate_soundtrack_wiki --uri "$CINESCRAPPER_MONGO_URI"
```

This is a dry run. If the counts and conflict list are expected, apply:

```bash
python -m cinescrapper.migrate_soundtrack_wiki --uri "$CINESCRAPPER_MONGO_URI" --apply
```

The migration renames `soundtrack` to `soundtrack_wiki` only when `soundtrack_wiki` does not already exist. It does not merge or overwrite a pre-existing `soundtrack_wiki`.

## 2. Scan a language library

Example for Thamizh:

```bash
python -m cinescrapper.scan_library \
  --base-path "/your/music/root/Thamizh" \
  --language-code ta \
  --output reports/Thamizh-library-scan.json
```

Use your real language-root path. `relative_path` is relative to that root. The scanner includes direct audio files and audio files under `Original Soundtrack`; it excludes `Background Score` and other named folders.

## 3. Reconcile local tracks into `soundtrack`

Dry run:

```bash
python -m cinescrapper.reconcile_soundtracks \
  --manifest reports/Thamizh-library-scan.json \
  --mongo-uri "$CINESCRAPPER_MONGO_URI" \
  --mongo-db cinescrapper \
  --report-dir reports/Thamizh-reconciliation
```

Review the generated CSV reports, especially `soundtrack_cinemas_not_found.csv` and `soundtrack_match_review.csv`.

Apply only after the dry-run output looks correct:

```bash
python -m cinescrapper.reconcile_soundtracks \
  --manifest reports/Thamizh-library-scan.json \
  --mongo-uri "$CINESCRAPPER_MONGO_URI" \
  --mongo-db cinescrapper \
  --report-dir reports/Thamizh-reconciliation \
  --apply
```

The local `soundtrack` object is written in this minimal form:

```json
{
  "tracks": [
    {
      "fileName": "01 - Song Name.m4a",
      "relative_path": "2020-30/2026/Movie [2026]/01 - Song Name.m4a",
      "add_collection": false
    }
  ]
}
```

Existing `add_collection` selections are preserved for matching relative paths. Tracks absent from a later scan are not automatically deleted.

## 4. Find local cinema folders missing from MongoDB

Export candidates:

```bash
python -m cinescrapper.export_local_cinema_candidates \
  --manifest reports/Thamizh-library-scan.json \
  --uri "$CINESCRAPPER_MONGO_URI" \
  --output reports/local_cinemas_for_review.json
```

Inspect every `possible_matches` array. This is especially important for multilingual films: a similar title can be the same film under a different language name, or a genuinely different film. Change `"status": "review"` to `"status": "approved"` only when you have confirmed the cinema should be a separate MongoDB record.

Dry-run import:

```bash
python -m cinescrapper.import_local_cinemas \
  --input reports/local_cinemas_for_review.json \
  --uri "$CINESCRAPPER_MONGO_URI"
```

Apply after reviewing:

```bash
python -m cinescrapper.import_local_cinemas \
  --input reports/local_cinemas_for_review.json \
  --uri "$CINESCRAPPER_MONGO_URI" \
  --apply
```

This import creates a minimal cinema document with `title`, `year`, `downloaded: false`, `add_collection: false`, and local `soundtrack.tracks`. It does not modify existing documents or create Wikipedia metadata in `soundtrack_wiki`. You can scrape the relevant language Wikipedia page later to enrich the new record.

## MongoDB URI

The commands above use the URI from `CINESCRAPPER_MONGO_URI`. If your `.env` file defines it, load it into the shell first:

```bash
set -a
source .env
set +a
```

Do not print or share your URI because it may contain credentials.
