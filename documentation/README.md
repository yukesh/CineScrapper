# CineScrapperPy documentation

Start with the project [README](../README.md) for installation and the quick start. This directory contains configuration and operational references.

## Guides

- [Configuration](ENVIRONMENT_CONFIGURATION.md): properties file keys, defaults, and credential handling.
- [Command reference](CineScrapper-Command-Reference.md): scraper options and common commands.
- [Missing cinemas workflow](MISSING_CINEMAS_WORKFLOW.md): review and import missing records.
- [Soundtrack refresh workflow](SOUNDTRACK_REFRESH_WORKFLOW.md): refresh soundtrack metadata.
- [Soundtrack migration workflow](SOUNDTRACK_MIGRATION_WORKFLOW.md): migrate or reconcile soundtrack data.
- [Collection copy workflow](COLLECTION_COPY_WORKFLOW.md): copy tracks marked for collection, with matching LRC files.
- [Updated flags](UPDATED_FLAGS.md): CLI flag changes.
- [Implementation notes](IMPLEMENTATION_0.2.0.md): historical implementation notes.

## Supported languages

Use `--language` with one of `thamizh`, `hindi`, `telugu`, `malayalam`, or `kannada`. The value is lowercase and is also the default MongoDB collection name. `--wiki-source` can override the corresponding Wikipedia master page.
