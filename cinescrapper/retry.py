"""Retry helpers for transient HTTP failures."""

from __future__ import annotations

import random
import time
from typing import Callable, Optional

from cinescrapper.logger import get_logger

logger = get_logger()


class RetryableHttpError(Exception):
    def __init__(self, status_code: int, retry_after: Optional[float] = None):
        super().__init__(f"HTTP {status_code}")
        self.status_code = status_code
        self.retry_after = retry_after


def parse_retry_after(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def backoff_seconds(attempt: int, base: float, maximum: float) -> float:
    return min(maximum, (base ** attempt) + random.uniform(0.0, 1.0))


def run_with_retry(
    operation: Callable[[], object],
    *,
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> object:
    """Run an operation with bounded exponential backoff."""
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            return operation()
        except RetryableHttpError as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            delay = exc.retry_after if exc.retry_after is not None else backoff_seconds(attempt, base_delay, max_delay)
            logger.warning("HTTP %s; retry %d/%d after %.1fs", exc.status_code, attempt, max_attempts, delay)
            time.sleep(delay)
        except retry_exceptions as exc:
            last_error = exc
            if attempt >= max_attempts:
                break
            delay = backoff_seconds(attempt, base_delay, max_delay)
            logger.warning("Transient error; retry %d/%d after %.1fs: %s", attempt, max_attempts, delay, exc)
            time.sleep(delay)
    raise last_error
