"""Read MongoDB and scraper settings from properties and process environment."""

from __future__ import annotations

import configparser
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROPERTIES_FILE = PROJECT_ROOT / "cinescrapper.properties"


def load_properties() -> configparser.ConfigParser:
    """Load settings without depending on the process working directory."""
    settings = configparser.ConfigParser(interpolation=None)
    if PROPERTIES_FILE.exists():
        settings.read(PROPERTIES_FILE, encoding="utf-8")
    return settings


def mongo_uri_profiles() -> dict[str, str]:
    """Return named profiles mapped to environment-variable names."""
    settings = load_properties()
    if not settings.has_section("mongodb.uris"):
        return {}
    return {name.lower(): env_name.strip() for name, env_name in settings["mongodb.uris"].items()}


def mongo_settings(profile: str | None = None) -> dict[str, str | None]:
    """Resolve MongoDB settings, preferring properties over generic env values.

    A selected named URI profile reads the URI from the environment variable
    named in ``[mongodb.uris]``. MONGODB_URI and ``[mongodb] uri`` are fallbacks.
    """
    properties = load_properties()
    configured_profile = profile or properties.get("mongodb", "uri_profile", fallback="").strip()
    uri = None
    if configured_profile:
        profiles = mongo_uri_profiles()
        env_name = profiles.get(configured_profile.lower())
        if env_name is None:
            available = ", ".join(sorted(profiles)) or "none configured"
            raise ValueError(
                f"Unknown MongoDB URI profile '{configured_profile}'. Available profiles: {available}."
            )
        uri = os.getenv(env_name)

    uri = uri or os.getenv("MONGODB_URI") or properties.get("mongodb", "uri", fallback=None)
    database = properties.get("mongodb", "database", fallback=None) or os.getenv("MONGODB_DATABASE")
    collection = properties.get("mongodb", "collection", fallback=None) or os.getenv("MONGODB_COLLECTION")
    return {"uri": uri, "database": database, "collection": collection}


def load_project_env() -> Path:
    """Populate legacy utility-script names from resolved settings."""
    settings = mongo_settings()
    aliases = {
        "CINESCRAPPER_MONGO_URI": settings["uri"],
        "CINESCRAPPER_MONGODB_DATABASE": settings["database"],
        "CINESCRAPPER_MONGODB_COLLECTION": settings["collection"],
    }
    for name, value in aliases.items():
        if value:
            os.environ[name] = value
        else:
            os.environ.pop(name, None)
    return PROPERTIES_FILE


def add_mongo_uri_profile_argument(parser) -> None:
    """Add a profile selector to a MongoDB-backed CLI."""
    profiles = sorted(mongo_uri_profiles())
    parser.add_argument(
        "--mongo-uri-profile",
        choices=profiles or None,
        help="Select a URI profile configured in [mongodb.uris].",
    )


def resolve_mongo_settings(
    *,
    uri: str | None = None,
    database: str | None = None,
    collection: str | None = None,
    profile: str | None = None,
) -> dict[str, str]:
    """Resolve and validate the connection settings for a MongoDB command."""
    configured = mongo_settings(profile)
    resolved = {
        "uri": uri or configured["uri"],
        "database": database or configured["database"],
        "collection": collection or configured["collection"],
    }
    missing = [name for name, value in resolved.items() if not value]
    if missing:
        details = []
        if "uri" in missing:
            selected_profile = profile or load_properties().get("mongodb", "uri_profile", fallback="").strip()
            env_name = mongo_uri_profiles().get(selected_profile.lower()) if selected_profile else None
            if env_name:
                details.append(
                    f"URI profile '{selected_profile}' reads environment variable "
                    f"{env_name}, which is not set in this process"
                )
            elif selected_profile:
                details.append(f"URI profile '{selected_profile}' is not configured in [mongodb.uris]")
            else:
                details.append("set MONGODB_URI or select a configured URI profile")
        raise ValueError(
            "MongoDB settings are missing: " + ", ".join(missing) + ". "
            + "; ".join(details)
            + ". Configure the missing values in cinescrapper.properties or pass the matching command-line options."
        )
    return {key: str(value) for key, value in resolved.items()}
