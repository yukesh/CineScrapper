# Environment configuration

CineScrapper scripts load `.env` from the repository root via `cinescrapper.env.load_project_env()` before reading environment-backed settings. This works even when a command is launched from another working directory, as long as the project is run from its source checkout.

1. Copy `.env.example` to `.env`.
2. Set `CINESCRAPPER_MONGO_URI` to the local/tunnel/Tailscale MongoDB URI you use.
3. Optionally set `CINESCRAPPER_MONGODB_DATABASE` and `CINESCRAPPER_MONGODB_COLLECTION`.
4. Run the normal script command; no `source .env` is required.

Supported aliases are `MONGODB_URI`, `MONGODB_DATABASE`, and `MONGODB_COLLECTION`. `CINESCRAPPER_*` values take precedence over the aliases. Existing shell variables take precedence over `.env` values. CLI arguments take precedence over both.

Never commit the real `.env`; it is ignored by Git. Commit only `.env.example` with placeholder values.
