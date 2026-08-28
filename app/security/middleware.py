from __future__ import annotations

from uuid import uuid4

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": (
        "default-src 'self'; "
        "base-uri 'self'; "
        "connect-src 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'; "
        "img-src 'self' data:; "
        "object-src 'none'; "
        "script-src 'self'; "
        "style-src 'self'"
    ),
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


class RequestTooLargeError(Exception):
    pass


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, enable_hsts: bool = False) -> None:
        self.app = app
        self.enable_hsts = enable_hsts

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid4().hex

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                path = str(scope.get("path", ""))
                for name, value in SECURITY_HEADERS.items():
                    if name == "Content-Security-Policy" and path in {"/docs", "/redoc"}:
                        continue
                    headers[name] = value
                if self.enable_hsts:
                    headers["Strict-Transport-Security"] = (
                        "max-age=31536000; includeSubDomains"
                    )
                headers["X-Request-ID"] = request_id
                if path.startswith("/api/"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, send_with_headers)


class RequestBodyLimitMiddleware:
    """Limita el cuerpo incluso si llega en varios frames ASGI."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        if max_bytes < 1:
            raise ValueError("max_bytes debe ser >= 1.")
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        content_length = headers.get("content-length")
        if content_length is not None:
            try:
                parsed_length = int(content_length)
                if parsed_length < 0:
                    await self._reject(send, status=400, detail="Solicitud inválida.")
                    return
                if parsed_length > self.max_bytes:
                    await self._reject(send)
                    return
            except ValueError:
                await self._reject(send, status=400, detail="Solicitud inválida.")
                return

        consumed = 0

        async def limited_receive() -> Message:
            nonlocal consumed
            message = await receive()
            if message["type"] == "http.request":
                body = message.get("body", b"")
                consumed += len(body)
                if consumed > self.max_bytes:
                    raise RequestTooLargeError
            return message

        try:
            await self.app(scope, limited_receive, send)
        except RequestTooLargeError:
            await self._reject(send)

    @staticmethod
    async def _reject(
        send: Send,
        *,
        status: int = 413,
        detail: str = "El cuerpo de la solicitud excede el límite permitido.",
    ) -> None:
        import json

        body = json.dumps({"detail": detail}, ensure_ascii=False).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json; charset=utf-8"),
                    (b"content-length", str(len(body)).encode("ascii")),
                    (b"cache-control", b"no-store"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
