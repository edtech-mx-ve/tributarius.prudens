from __future__ import annotations

import json
from typing import Any

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.services.public_response_quality_19s_r16 import normalize_public_value
from app.services.trace_integrity_19s_r16 import reconcile_traceability_payload


class PublicUnicodeNormalizationMiddleware:
    """Normaliza JSON público y reconcilia trazabilidad sin alterar el dominio."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        messages: list[Message] = []

        async def capture(message: Message) -> None:
            messages.append(message)

        await self.app(scope, receive, capture)

        if not _is_json_response(messages):
            for message in messages:
                await send(message)
            return

        body = b"".join(
            message.get("body", b"")
            for message in messages
            if message["type"] == "http.response.body"
        )
        normalized = _normalize_json_bytes(body)
        if normalized is None:
            for message in messages:
                await send(message)
            return

        start = next(
            message for message in messages if message["type"] == "http.response.start"
        )
        headers = [
            (name, value)
            for name, value in start.get("headers", [])
            if name.lower() not in {b"content-length", b"content-type"}
        ]
        headers.extend(
            [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(normalized)).encode("ascii")),
            ]
        )
        await send(
            {
                "type": "http.response.start",
                "status": start["status"],
                "headers": headers,
            }
        )
        await send({"type": "http.response.body", "body": normalized})


def _is_json_response(messages: list[Message]) -> bool:
    for message in messages:
        if message["type"] != "http.response.start":
            continue
        for name, value in message.get("headers", []):
            if name.lower() == b"content-type":
                return b"application/json" in value.lower()
    return False


def _normalize_json_bytes(body: bytes) -> bytes | None:
    try:
        payload: Any = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None

    reconciled = reconcile_traceability_payload(payload)
    normalized = normalize_public_value(reconciled)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
