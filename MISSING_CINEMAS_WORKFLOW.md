# Find and import missing cinema records

These commands compare Wikipedia's yearly lists with the existing MongoDB `cinescrapper.cinemas` collection. The export command is read-only; importing is a separate, explicit step.

## 1. Export candidates (read-only)

From the project root, activate the project virtual environment and ensure your existing `.env` or shell has the correct `CINESCRAPPER_MONGO_URI` (or `MONGODB_URI`). Do not put credentials into a shared command or commit them.

```bash
python -m cinescrapper.export_missing_cinemas \
  --start-year 1920 --end-year 2026 \
  --output reports/missing_cinemas_1920_2026.json
```

The script creates three files beside the requested output:

- `missing_cinemas_1920_2026.json`: candidates without an exact or high-similarity same-year match. Each item starts with `"status": "review"`.
- `possible_matches_1920_2026.json`: candidates that resemble existing titles and need manual review. This file is not imported automatically.
- `audit_summary_1920_2026.json`: counts, failed/empty years and confirmation that MongoDB was not modified.

A year that returns no parsed movies is marked for review, not treated as proof that no movies exist. Check `failed_or_empty_years` in the summary before relying on the report.

## 2. Review the missing list

Open the missing JSON file and change `"status": "review"` to `"status": "approved"` only for each entry you have manually verified. Keep possible matches separate until you determine whether they are duplicates or different films. The script never auto-imports the possible-matches report.

## 3. Dry-run the import

```bash
python -m cinescrapper.import_missing_cinemas \
  --input reports/missing_cinemas_1920_2026.json
```

The importer only considers entries with `status` set to `approved`. It checks normalized title + year against the current collection and defaults missing `downloaded`, cinema-level `add_collection`, soundtrack-level `add_collection`, and track-level `add_collection` fields to `False`. It does not overwrite an existing cinema record.

## 4. Apply the import

Only after checking the dry-run output:

```bash
python -m cinescrapper.import_missing_cinemas \
  --input reports/missing_cinemas_1920_2026.json --apply
```

Then audit the flag defaults if required:

```bash
python -m cinescrapper.audit_cinema_fields
python -m cinescrapper.audit_cinema_fields --apply
```

The audit's `--apply` mode fills only fields that are absent; existing `True` and `False` values are preserved.
