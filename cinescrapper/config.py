"""Runtime configuration loaded from the project properties file and CLI."""

from __future__ import annotations

from dataclasses import dataclass

from cinescrapper.env import load_properties





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
    def from_properties(cls) -> "ScraperConfig":
        values = load_properties()
        section = values["scraper"] if values.has_section("scraper") else {}
        return cls(
            batch_size=int(section.get("batch_size", 10)),
            wiki_rate_limit=float(section.get("wiki_rate_limit", 1.5)),
            apple_music_rate_limit=float(section.get("apple_music_rate_limit", 2.0)),
            rate_limit_jitter=float(section.get("rate_limit_jitter", 0.25)),
            max_retries=int(section.get("max_retries", 3)),
            retry_base_delay=float(section.get("retry_base_delay", 2.0)),
            retry_max_delay=float(section.get("retry_max_delay", 60.0)),
            cache_ttl_seconds=int(section.get("cache_ttl_seconds", 604800)),
            request_timeout=float(section.get("request_timeout", 15.0)),
        )

    def validate(self) -> None:
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.max_retries < 1:
            raise ValueError("max_retries must be >= 1")
        if self.wiki_rate_limit < 0 or self.apple_music_rate_limit < 0:
            raise ValueError("rate limits must be >= 0")
