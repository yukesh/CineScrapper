# Local soundtrack refresh workflow

The local `soundtrack` field is rebuilt from the current local-library manifest. Wikipedia metadata stays in `soundtrack_wiki`.

## 1. Scan the library

```bash
python -m cinescrapper.scan_library \
  --base-path "/path/to/music/Thamizh" \
  --language-code ta \
  --output reports/Thamizh-library-scan.json
```

Use your actual language-root path. The manifest should reflect the current filenames and relative paths.

## 2. Dry-run the refresh

```bash
python -m cinescrapper.reconcile_soundtracks \
  --manifest reports/Thamizh-library-scan.json \
  --mongo-uri "$CINESCRAPPER_MONGO_URI" \
  --mongo-db cinescrapper \
  --report-dir reports/Thamizh-refresh
```

No MongoDB changes are made without `--apply`.

Reports include:

- `soundtrack_tracks_added.csv`: tracks present in the scan but not at the same relative path in MongoDB.
- `soundtrack_tracks_removed.csv`: previous tracks no longer present at the same relative path. A renamed/moved file typically appears as one removal and one addition.
- `soundtrack_cinemas_not_found.csv` and `soundtrack_match_review.csv`: unmatched/ambiguous local cinema folders that were not updated.
- `soundtrack_reconciliation_summary.csv`: counts for the run.

## 3. Apply the refresh

After reviewing all reports, rerun the same command with `--apply`.

For each safely matched local cinema folder, this replaces the entire `soundtrack` object with `{ "tracks": [...] }` from the current manifest and sets `downloaded: true`. The `soundtrack_wiki` field is not modified. A matched folder with no supported audio files will receive an empty `tracks` array and `downloaded: true`.

`add_collection` is preserved only when a track's relative path is unchanged. New, renamed, or moved tracks default to `false`; tracks no longer present locally are removed from the rebuilt `soundtrack` node. Make a MongoDB backup before applying if you need to retain the previous track selections/history.
