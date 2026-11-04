# CineScrapperPy

CineScrapperPy collects cinema and soundtrack metadata from Wikipedia and Apple Music and can store the results in MongoDB.

## Quick start

1. Use Python 3.12 or newer and install the project:

   ```sh
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. Create `cinescrapper.properties` in the project root and map each URI profile to an environment-variable name. Set the URI values in your environment; the properties file is ignored by Git.
3. Scrape a year and save results to MongoDB:

   ```sh
   cinescrapper --language thamizh --year 2026 --mongo-enabled
   ```

Without `--mongo-enabled`, the scraper reports progress without writing to MongoDB. Language names are lowercase: `thamizh`, `hindi`, `telugu`, `malayalam`, and `kannada`. Each language writes to a collection with the same lowercase name in the configured database (`hindi` writes to `hindi`). Pass `--mongo-collection` to override the collection for a run.

## Configuration

Persistent settings use `cinescrapper.properties`; URI secrets remain in environment variables. The properties file is ignored by Git. CLI flags override property values. See [Configuration](documentation/ENVIRONMENT_CONFIGURATION.md).

## Documentation

- [Documentation index](documentation/README.md)
- [Command reference](documentation/CineScrapper-Command-Reference.md)
- [Configuration](documentation/ENVIRONMENT_CONFIGURATION.md)
- [Missing cinemas workflow](documentation/MISSING_CINEMAS_WORKFLOW.md)
- [Implementation notes](documentation/IMPLEMENTATION_0.2.0.md)
- [Soundtrack refresh workflow](documentation/SOUNDTRACK_REFRESH_WORKFLOW.md)
- [Soundtrack migration workflow](documentation/SOUNDTRACK_MIGRATION_WORKFLOW.md)
- [Collection copy workflow](documentation/COLLECTION_COPY_WORKFLOW.md)
- [Updated flags](documentation/UPDATED_FLAGS.md)
- [Configuration change notes](documentation/UPDATE-NOTES-ENV.md)

## Docker

Start MongoDB with `docker compose up -d mongo`. For the bundled service, set `MONGODB_URI_MYLOCAL=mongodb://mongo:27017` in the environment, then run `docker compose --profile scraper run --rm scraper --language hindi --year 2026`.
