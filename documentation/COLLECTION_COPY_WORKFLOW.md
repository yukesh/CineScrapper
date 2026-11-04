# Collection copy workflow

`copy_collection_tracks` stages selected local tracks in a target directory. It reads MongoDB's `soundtrack.tracks` entries and copies only tracks with `add_collection: true`.

## Preview and copy

Run from the project root. `--source-root` must be the same library root used to create the track `relative_path` values. MongoDB connection settings are resolved using `cinescrapper.properties` and the configured environment-variable URI profile.

```bash
python -m cinescrapper.copy_collection_tracks \
  --source-root "/your/music/root/Thamizh" \
  --target-folder "/your/collection"
```

This is a dry run and prints every source and destination. Add `--apply` to perform the copy:

```bash
python -m cinescrapper.copy_collection_tracks \
  --source-root "/your/music/root/Thamizh" \
  --target-folder "/your/collection" \
  --apply
```

The target layout is:

- One selected track for a cinema: `<target>/<year>/<track filename>`.
- Multiple selected tracks for a cinema: `<target>/<year>/<cinema title> [<year>]/<track filename>`.

If a same-stem `.lrc` file exists next to an audio file, it is included beside the copied audio. Existing target files are never overwritten; the command stops and reports a collision so you can inspect it before retrying. Use `--uri`, `--database`, `--collection`, or `--mongo-uri-profile` to override the configured MongoDB target for a run.
