import time

from cinescrapper.rate_limiter import RateLimiter


def test_rate_limiter_enforces_interval():
    limiter = RateLimiter(0.05, 0)
    limiter.acquire()
    started = time.monotonic()
    limiter.acquire()
    assert time.monotonic() - started >= 0.045
