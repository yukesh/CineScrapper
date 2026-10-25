"""Runtime configuration loaded from CLI arguments and environment variables."""

from __future__ import annotations

from cinescrapper.env import load_project_env

load_project_env()


import os
from dataclasses import dataclass



def _env_float(name: str, default: float) -> float:
    return float(os.getenv(name, default))


def _env_int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class ScraperConfig:
    batch_size: int = 10
    wiki_rate_limit: float = 1.5
    apple_music_rate_limit: float = 2.0
    rate_limit_jitter: float = 0.25
    max_retries: int = 3
    retry_base_delay: float = 2.0
    retry_max_delay: float = 60.0
    cache_ttl_seconds: int = 7 * 24 * 60 * 60
    request_timeout: float = 15.0
    force: bool = False
    resume: bool = False

    @classmethod
    def from_env(cls) -> "ScraperConfig":
        return cls(
            batch_size=_env_int("CINESCRAPPER_BATCH_SIZE", 10),
            wiki_rate_limit=_env_float("CINESCRAPPER_WIKI_RATE_LIMIT", 1.5),
            apple_music_rate_limit=_env_float("CINESCRAPPER_APPLE_MUSIC_RATE_LIMIT", 2.0),
            rate_limit_jitter=_env_float("CINESCRAPPER_RATE_LIMIT_JITTER", 0.25),
            max_retries=_env_int("CINESCRAPPER_MAX_RETRIES", 3),
            retry_base_delay=_env_float("CINESCRAPPER_RETRY_BASE_DELAY", 2.0),
            retry_max_delay=_env_float("CINESCRAPPER_RETRY_MAX_DELAY", 60.0),
            cache_ttl_seconds=_env_int("CINESCRAPPER_CACHE_TTL", 7 * 24 * 60 * 60),
            request_timeout=_env_float("CINESCRAPPER_REQUEST_TIMEOUT", 15.0),
            force=os.getenv("CINESCRAPPER_FORCE", "false").lower() in {"1", "true", "yes", "y"},
            resume=os.getenv("CINESCRAPPER_RESUME", "false").lower() in {"1", "true", "yes", "y"},
        )

    def validate(self) -> None:
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        if self.wiki_rate_limit < 0 or self.apple_music_rate_limit < 0:
            raise ValueError("rate limits must be >= 0")
