"""Simple thread-safe minimum-interval rate limiter."""

from __future__ import annotations

import random
import threading
import time

from cinescrapper.logger import get_logger

logger = get_logger()


class RateLimiter:
    """Ensure a minimum interval between requests made through this limiter."""

    def __init__(self, min_interval: float = 1.5, jitter: float = 0.25):
        if min_interval < 0:
            raise ValueError("min_interval must be >= 0")
        if jitter < 0:
            raise ValueError("jitter must be >= 0")
        self.min_interval = float(min_interval)
        self.jitter = float(jitter)
        self._last_request = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self.min_interval - (now - self._last_request)
            if wait > 0:
                wait += random.uniform(0, self.jitter)
                logger.debug("Rate limiter waiting %.2f seconds", wait)
                time.sleep(wait)
            self._last_request = time.monotonic()
