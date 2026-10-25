"""Load CineScrapper's project-root environment configuration consistently."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_project_env() -> Path:
    """Load the repository's .env regardless of the shell's current directory.

    Existing shell variables take precedence over values in .env. The function
    is safe to call repeatedly and returns the path used for easier diagnostics.
    """
    load_dotenv(dotenv_path=ENV_FILE, override=False)
    return ENV_FILE


def mongo_settings() -> dict[str, str]:
    """Return MongoDB settings using the project's supported environment names."""
    load_project_env()
    return {
        "uri": (
            os.getenv("CINESCRAPPER_MONGO_URI")
            or os.getenv("MONGODB_URI")
            or "mongodb://localhost:27017"
        ),
        "database": (
            os.getenv("CINESCRAPPER_MONGODB_DATABASE")
            or os.getenv("MONGODB_DATABASE")
            or "cinescrapper"
        ),
        "collection": (
            os.getenv("CINESCRAPPER_MONGODB_COLLECTION")
            or os.getenv("MONGODB_COLLECTION")
            or "cinemas"
        ),
    }
