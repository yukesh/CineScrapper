# CineScrapper flag update

This update adds four persisted flags:

- `downloaded` (cinema): defaults to `False`; soundtrack reconciliation sets it to `True` when supported local audio tracks are found.
- `add_collection` (cinema): defaults to `False`.
- `soundtrack.add_collection`: defaults to `False`.
- `soundtrack.tracks[].add_collection`: defaults to `False`.

Updated files:
- `cinescrapper/cine_model.py`: dataclass fields and serialization.
- `cinescrapper/mongo_writer.py`: preserves existing flag values during normal scrapes, including track selections.
- `cinescrapper/reconcile_soundtracks.py`: keeps existing soundtrack/track flags and defaults the soundtrack flag only when missing. Existing reconciliation still updates `downloaded=True` when local audio is found.
- `cinescrapper/audit_cinema_fields.py`: audits all four flag locations; dry-run by default, `--apply` only fills missing values.

Apply these files over the matching paths in your existing `CineScrapper` checkout. Before changing existing MongoDB records, run:

```bash
python -m cinescrapper.audit_cinema_fields
```

Then, after reviewing the report, apply missing defaults:

```bash
python -m cinescrapper.audit_cinema_fields --apply
```

The audit never changes existing values. It does not mark `downloaded=True`; only soundtrack reconciliation does that when it finds local audio.
