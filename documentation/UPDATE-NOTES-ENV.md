Environment configuration update for CineScrapper 0.2.1-dev

- Added cinescrapper/env.py to load the project-root .env consistently regardless of current working directory.
- Applied the loader to scripts that read environment variables or MongoDB settings.
- Standardized support for CINESCRAPPER_MONGO_URI / MONGODB_URI and database/collection aliases.
- Made soundtrack reconciliation database and collection arguments default from .env instead of requiring the database argument.
- Updated the MongoDB ping helper so importing it does not initiate a live database connection.
- Added .env.example, environment documentation, and tests/test_env.py.
- Added python-dotenv to requirements.txt (it was already in pyproject.toml).

No real credentials are included. Copy .env.example to .env and edit it locally.
