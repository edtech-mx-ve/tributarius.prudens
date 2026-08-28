from __future__ import annotations

import re
import unicodedata

from pydantic import BaseModel, Field

_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "override_instructions",
        re.compile(
            r"\b(ignore|ignora|omite|olvida)\b.{0,40}"
            r"\b(previous|prior|anteriores?|previas?)\b.{0,20}"
            r"\b(instructions?|instrucciones?)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "hidden_prompt_request",
        re.compile(
            r"\b(system prompt|developer message|prompt del sistema|mensaje del desarrollador)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "secret_exfiltration",
        re.compile(
            r"\b(reveal|show|print|dump|muestra|revela|imprime)\b.{0,40}"
            r"\b(secret|secrets|hidden|internas?|ocultas?|instrucciones?)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "role_override",
        re.compile(
            r"\b(act as|behave as|actúa como|comportate como|compórtate como)\b.{0,30}"
            r"\b(system|developer|sistema|desarrollador)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class PromptInjectionAssessment(BaseModel):
    suspicious: bool
    indicators: list[str] = Field(default_factory=list, max_length=10)


def normalize_untrusted_text(value: str) -> str:
    """Normaliza texto sin convertirlo en instrucciones confiables."""
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    return normalized.strip()


def validate_text_safety(value: str, *, max_newlines: int = 80) -> str:
    """Rechaza controles invisibles y entradas anómalamente fragmentadas."""
    normalized = normalize_untrusted_text(value)
    if _CONTROL_CHARS.search(normalized):
        raise ValueError("La consulta contiene caracteres de control no permitidos.")
    if normalized.count("\n") > max_newlines:
        raise ValueError("La consulta contiene demasiados saltos de línea.")
    return normalized


def assess_prompt_injection(value: str) -> PromptInjectionAssessment:
    """Heurística defensiva; no es clasificador probabilístico ni prueba concluyente."""
    normalized = normalize_untrusted_text(value)
    indicators = [
        name
        for name, pattern in _INJECTION_PATTERNS
        if pattern.search(normalized) is not None
    ]
    return PromptInjectionAssessment(
        suspicious=bool(indicators),
        indicators=indicators,
    )
