import pytest

from app.security.rate_limit import InMemoryRateLimiter


def test_rate_limiter_enforces_window() -> None:
    limiter = InMemoryRateLimiter(max_requests=2, window_seconds=10)
    assert limiter.allow("client", now=100.0)
    assert limiter.allow("client", now=101.0)
    assert not limiter.allow("client", now=102.0)
    assert limiter.allow("client", now=111.1)


def test_rate_limiter_separates_keys() -> None:
    limiter = InMemoryRateLimiter(max_requests=1, window_seconds=10)
    assert limiter.allow("a", now=1.0)
    assert not limiter.allow("a", now=2.0)
    assert limiter.allow("b", now=2.0)


@pytest.mark.parametrize("requests,window", [(0, 10), (1, 0)])
def test_rate_limiter_rejects_invalid_configuration(requests: int, window: int) -> None:
    with pytest.raises(ValueError):
        InMemoryRateLimiter(requests, window)


def test_rate_limiter_bounds_distinct_keys() -> None:
    limiter = InMemoryRateLimiter(
        max_requests=2,
        window_seconds=10,
        max_keys=2,
    )
    assert limiter.allow("a", now=1.0)
    assert limiter.allow("b", now=1.0)
    assert not limiter.allow("c", now=2.0)
    assert limiter.allow("c", now=12.0)
