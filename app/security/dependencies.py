from __future__ import annotations

from functools import lru_cache
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from app.core.config import get_settings
from app.security.rate_limit import InMemoryRateLimiter


@lru_cache
def get_consultation_rate_limiter() -> InMemoryRateLimiter:
    settings = get_settings()
    return InMemoryRateLimiter(
        max_requests=settings.consultation_rate_limit,
        window_seconds=settings.consultation_rate_window_seconds,
    )


def enforce_consultation_rate_limit(request: Request) -> None:
    """Limita por IP observada por ASGI; no confía en X-Forwarded-For del cliente."""
    client_host = request.client.host if request.client is not None else "unknown"
    limiter = get_consultation_rate_limiter()
    if not limiter.allow(client_host):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiadas consultas. Inténtalo de nuevo más tarde.",
            headers={"Retry-After": str(get_settings().consultation_rate_window_seconds)},
        )


def enforce_same_origin(request: Request) -> None:
    """Rechaza orígenes de navegador que no coincidan con el Host recibido."""
    origin = request.headers.get("origin")
    if origin is None:
        return

    parsed = urlsplit(origin)
    origin_host = parsed.netloc.lower()
    request_host = request.headers.get("host", "").lower()
    if parsed.scheme not in {"http", "https"} or origin_host != request_host:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origen de solicitud no permitido.",
        )
