# CineScrapper 0.2.1-dev --- Command Reference

This guide consolidates the commands for the current CineScrapper
workflow. Commands assume the project is at `~/dev/repos/CineScrapper`,
the MongoDB database is `cinescrapper`, the collection is `cinemas`, and
all generated reports should go under `soundtrack_reports/`.

> **Safety:** Commands that change MongoDB are shown with a dry-run
> first. Do not add `--apply` or `--mongo-enabled` until you have
> checked the target URI and reviewed reports.

## 1. Start the project

``` bash
cd ~/dev/repos/CineScrapper
source venv/bin/activate
mkdir -p soundtrack_reports
```

Make sure your `.env` or shell environment has the correct connection
URI for your Windows-hosted MongoDB/SSH tunnel. Prefer
`CINESCRAPPER_MONGO_URI`. Do not paste credentials into reports or
source files.

For scripts that accept `--uri`, set a convenient shell variable:

``` bash
export MONGO_URI="${CINESCRAPPER_MONGO_URI:-${MONGODB_URI:-}}"
test -n "$MONGO_URI" || echo "Set CINESCRAPPER_MONGO_URI or MONGODB_URI before continuing"
```

For the audit script, set `MONGODB_URI` explicitly as well, because its
current CLI reads that variable:

``` bash
export MONGODB_URI="$MONGO_URI"
```

Confirm command options before running a workflow if your local files
differ:

``` bash
python -m cinescrapper.scan_library --help
python -m cinescrapper.reconcile_soundtracks --help
python -m cinescrapper.migrate_soundtrack_wiki --help
python -m cinescrapper.audit_cinema_fields --help
python -m cinescrapper.export_local_cinema_candidates --help
python -m cinescrapper.import_local_cinemas --help
python -m cinescrapper.export_missing_cinemas --help
python -m cinescrapper.import_missing_cinemas --help
python -m cinescrapper --help
```

## 2. One-time migration: `soundtrack` → `soundtrack_wiki`

The old `soundtrack` field contains Wikipedia-scraped data. Migrate it
before running the updated scraper or local soundtrack reconciliation.

### Dry run

``` bash
python -m cinescrapper.migrate_soundtrack_wiki \
  --uri "$MONGO_URI" \
  --database cinescrapper \
  --collection cinemas
```

Review the counts and any conflict rows. Documents that already contain
both `soundtrack` and `soundtrack_wiki` are intentionally left
untouched.

### Apply the rename

``` bash
python -m cinescrapper.migrate_soundtrack_wiki \
  --uri "$MONGO_URI" \
  --database cinescrapper \
  --collection cinemas \
  --apply
```

Run the dry run again afterward to verify that there are no remaining
safe renames. This is a one-time migration; do not run `--apply`
repeatedly as a routine scan.

## 3. Scrape Wikipedia data into `soundtrack_wiki`

The main scraper writes to MongoDB only when `--mongo-enabled` is
supplied. Run the appropriate year or range for your source.

### Example: scan a year range

``` bash
python -m cinescrapper \
  --wiki-source Lists_of_Tamil-language_films \
  --start-year 2020 \
  --end-year 2026 \
  --mongo-enabled \
  --mongo-uri "$MONGO_URI" \
  --mongo-db cinescrapper \
  --mongo-collection cinemas
```

For a single year, use `--year YYYY` instead of `--start-year` and
`--end-year`. Do not combine `--year` with a range. Use `--resume` to
skip already-completed jobs or `--force` to reprocess all movies. The
main scraper has no general dry-run flag in this CLI: `--mongo-enabled`
enables MongoDB writes.

## 4. Scan the local music library

The scanner creates a JSON manifest and does not write to MongoDB. Scan
the language root folder, not an individual movie folder. Supported
audio files are found in cinema folders and `Original Soundtrack`
subfolders; `Background Score` is excluded.

### Thamizh example

Replace the example path with your actual root:

``` bash
python -m cinescrapper.scan_library \
  --base-path "/Volumes/ALAC/Thamizh" \
  --language-code ta \
  --language-folder Thamizh \
  --output soundtrack_reports/library-scan-tamil.json
```

Language code examples: Tamil `ta`, Hindi `hi`, Kannada `kn`, Malayalam
`ml`, Telugu `te`. Use a distinct manifest filename for each language,
e.g. `library-scan-hindi.json`.

## 5. Refresh MongoDB `soundtrack` from the local scan

This is the recurring workflow after adding, renaming, moving, or
deleting local files. It rebuilds the local `soundtrack` node from the
manifest for safely matched cinema records. It does not change
`soundtrack_wiki`.

### Dry run (default)

``` bash
python -m cinescrapper.reconcile_soundtracks \
  --manifest soundtrack_reports/library-scan-tamil.json \
  --mongo-uri "$MONGO_URI" \
  --mongo-db cinescrapper \
  --mongo-collection cinemas \
  --report-dir soundtrack_reports
```

Review these reports in `soundtrack_reports/`:

-   `soundtrack_tracks_added.csv`
-   `soundtrack_tracks_removed.csv`
-   `soundtrack_cinemas_not_found.csv`
-   `soundtrack_match_review.csv`
-   `soundtrack_reconciliation_summary.csv`

The added/removed reports are reports of the proposed changes; they are
**not** the input that controls what gets written. `--apply` applies the
full refreshed track list for safely matched cinema records, not only
rows in the added CSV.

### Apply the refresh

Only after reviewing the dry-run reports:

``` bash
python -m cinescrapper.reconcile_soundtracks \
  --manifest soundtrack_reports/library-scan-tamil.json \
  --mongo-uri "$MONGO_URI" \
  --mongo-db cinescrapper \
  --mongo-collection cinemas \
  --report-dir soundtrack_reports \
  --apply
```

The current intended behaviour is to rebuild `soundtrack.tracks` from
the local manifest, reflecting file renames/moves and removals, and set
`downloaded: true` for safely matched cinema folders. Existing
`add_collection` values are preserved when the same relative path is
still present. A track with a new relative path defaults to
`add_collection: false`; a renamed track may therefore need its
selection re-applied. Back up MongoDB before the first apply.

## 6. Audit missing default fields

The audit script defaults to dry-run. It adds only fields that are
absent and should preserve existing `true`/`false` values.

### Dry run

``` bash
python -m cinescrapper.audit_cinema_fields \
  --uri "$MONGO_URI" \
  --database cinescrapper \
  --collection cinemas
```

### Apply defaults

``` bash
python -m cinescrapper.audit_cinema_fields \
  --uri "$MONGO_URI" \
  --database cinescrapper \
  --collection cinemas \
  --apply
```

### Verify

``` bash
python -m cinescrapper.audit_cinema_fields \
  --uri "$MONGO_URI" \
  --database cinescrapper \
  --collection cinemas
```

Defaults audited include cinema-level `downloaded` and `add_collection`,
plus `add_collection` on a `soundtrack` object and its track entries
when those structures exist. Run this after importing new cinema
records. The audit's current argument names are `--uri`, `--database`,
and `--collection`.

## 7. Find local cinema folders missing from MongoDB

Use this for multilingual films or local albums whose cinema is not yet
in the database. First generate a local scan manifest (Section 4).

### Export candidates

``` bash
python -m cinescrapper.export_local_cinema_candidates \
  --manifest soundtrack_reports/library-scan-tamil.json \
  --uri "$MONGO_URI" \
  --database cinescrapper \
  --collection cinemas \
  --output soundtrack_reports/local_cinemas_for_review.json
```

Review the JSON's `possible_matches` carefully. For a multilingual film,
approve a new cinema only when it really is a separate record and not an
existing film with another language title. Set `"status": "approved"`
for verified entries you want to insert; leave uncertain candidates for
review.

### Dry-run import

``` bash
python -m cinescrapper.import_local_cinemas \
  --input soundtrack_reports/local_cinemas_for_review.json \
  --uri "$MONGO_URI" \
  --database cinescrapper \
  --collection cinemas
```

### Apply approved local-only cinemas

``` bash
python -m cinescrapper.import_local_cinemas \
  --input soundtrack_reports/local_cinemas_for_review.json \
  --uri "$MONGO_URI" \
  --database cinescrapper \
  --collection cinemas \
  --apply
```

After inserting new records, rerun the soundtrack reconciliation dry run
and review it before applying, so the local soundtrack is built for the
new cinema documents too.

## 8. Find Wikipedia films missing from MongoDB

This is separate from local-folder discovery. It scans Wikipedia's film
list for a year range, compares titles/years against MongoDB, and
exports missing films plus possible matches and an audit summary.

### Export a range

``` bash
python -m cinescrapper.export_missing_cinemas \
  --start-year 1920 \
  --end-year 2026 \
  --uri "$MONGO_URI" \
  --database cinescrapper \
  --collection cinemas \
  --output soundtrack_reports/missing_cinemas_1920_2026.json
```

The script also creates `possible_matches_1920_2026.json` and
`audit_summary_1920_2026.json` alongside the requested output file.
Review all three. Possible matches are for manual review and are not
imported by the missing-cinema importer.

### Approve verified missing entries

In `soundtrack_reports/missing_cinemas_1920_2026.json`, set
`"status": "approved"` only for entries verified as genuinely missing.
Leave uncertain entries as `"review"`.

### Dry-run import

``` bash
python -m cinescrapper.import_missing_cinemas \
  --input soundtrack_reports/missing_cinemas_1920_2026.json \
  --uri "$MONGO_URI" \
  --database cinescrapper \
  --collection cinemas
```

### Apply approved missing entries

``` bash
python -m cinescrapper.import_missing_cinemas \
  --input soundtrack_reports/missing_cinemas_1920_2026.json \
  --uri "$MONGO_URI" \
  --database cinescrapper \
  --collection cinemas \
  --apply
```

Run the field audit after importing to add any missing defaults.
Possible-match entries are intentionally not imported by this script.

## 9. Recommended routine

For normal local music-library changes:

1.  Scan library → create/update the JSON manifest.
2.  Reconcile dry run → review all CSV reports.
3.  Reconcile with `--apply` → rebuild local `soundtrack` and mark
    matched cinemas downloaded.
4.  Run `audit_cinema_fields.py` dry-run; apply only if it reports
    missing defaults.

For a one-time migration, rename `soundtrack` to `soundtrack_wiki`
first. For new Wikipedia scraping, use the main scraper with
`--mongo-enabled`. For local-only cinema entries or Wikipedia-discovered
missing films, use the relevant export → review/approve → dry-run import
→ `--apply` workflow.

## 10. Quick safety checklist

-   Confirm `$MONGO_URI` points to the intended MongoDB instance before
    any write.
-   Back up MongoDB before the one-time migration and before the first
    full soundtrack refresh.
-   Never use `--apply` until dry-run output and reports have been
    reviewed.
-   Do not treat `soundtrack_tracks_added.csv` as an apply queue;
    reconciliation applies the full refreshed track list.
-   `soundtrack_wiki` is the Wikipedia metadata node; `soundtrack` is
    the local-library node.
-   Preserve the JSON manifest and reports for each scan so changes can
    be reviewed later.
