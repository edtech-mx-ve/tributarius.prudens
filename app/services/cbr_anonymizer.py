from __future__ import annotations

import re

from app.domain.cbr import AnonymizationResult

PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "email",
        re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b"),
    ),
    (
        "rfc",
        re.compile(r"(?i)\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}\b"),
    ),
    (
        "curp",
        re.compile(
            r"(?i)\b[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d\b"
        ),
    ),
)


def anonymize_text(text: str) -> AnonymizationResult:
    """Redacta identificadores obvios; exige revisión humana posterior."""
    clean = text.strip()
    if not clean:
        raise ValueError("El texto a anonimizar no puede estar vacío.")

    detected: list[str] = []
    count = 0
    result = clean
    for kind, pattern in PATTERNS:
        result, substitutions = pattern.subn(f"[REDACTED_{kind.upper()}]", result)
        if substitutions:
            detected.append(kind)
            count += substitutions

    return AnonymizationResult(
        text=result,
        redaction_count=count,
        detected_types=detected,
        requires_human_review=True,
    )
