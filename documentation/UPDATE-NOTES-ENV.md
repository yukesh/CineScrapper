# Configuration change notes

URI profiles in `[mongodb.uris]` map profile names to environment-variable names. The actual URI values stay in the environment. The `cinescrapper.properties.example` template was removed; create the local properties file yourself. The file is ignored by Git.

All MongoDB commands use the shared resolver for URI, database, and collection selection. Missing required values produce a clear error instead of silently connecting to localhost or a generic default database. The scraper still selects its collection from the lowercase language unless `--mongo-collection` is provided. See the [configuration guide](ENVIRONMENT_CONFIGURATION.md) and [command reference](CineScrapper-Command-Reference.md).
