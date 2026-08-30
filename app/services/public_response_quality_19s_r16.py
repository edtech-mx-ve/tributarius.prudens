from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

_SUSPICIOUS = ("Ã", "Â", "â€", "â€“", "â€”", "â€œ", "â€™")

# Algunas salidas históricas ya perdieron el segundo carácter del mojibake
# (p. ej. U+00AD puede desaparecer al copiar/renderizar). Ese daño no es
# reversible por recodificación; sólo corregimos formas observadas y no ambiguas.
_OBSERVED_LOSSY_REPAIRS = {
    "PolÃtica": "Política",
    "polÃtica": "política",
    "jurÃdica": "jurídica",
    "JurÃdica": "Jurídica",
    "Ãndice": "Índice",
    "ÃNDICE": "ÍNDICE",
    "ArtÃculo": "Artículo",
    "artÃculo": "artículo",
    "mÃnimo": "mínimo",
    "MÃnimo": "Mínimo",
    "cÃ¡lculo": "cálculo",
    "CÃ¡lculo": "Cálculo",
    "ResoluciÃ³n": "Resolución",
    "resoluciÃ³n": "resolución",
}


def _damage_score(value: str) -> int:
    return sum(value.count(marker) for marker in _SUSPICIOUS)


def _lossy_observed_repair(value: str) -> str:
    repaired = value
    for damaged, correct in _OBSERVED_LOSSY_REPAIRS.items():
        repaired = repaired.replace(damaged, correct)
    return repaired


def _candidate_repairs(value: str) -> tuple[str, ...]:
    candidates: list[str] = []
    for encoding in ("cp1252", "latin-1"):
        try:
            repaired = value.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if repaired not in candidates:
            candidates.append(repaired)
    return tuple(candidates)


def repair_mojibake(value: str) -> str:
    """Repara mojibake reversible y formas truncadas observadas en producción."""
    if not value or not any(marker in value for marker in _SUSPICIOUS):
        return value

    best = value
    best_score = _damage_score(value)
    for candidate in _candidate_repairs(value):
        score = _damage_score(candidate)
        if score < best_score:
            best = candidate
            best_score = score

    # Si la recodificación no puede reconstruir bytes ya perdidos, aplica sólo
    # el vocabulario observado. No intenta adivinar secuencias ambiguas.
    repaired = _lossy_observed_repair(best)
    return repaired if _damage_score(repaired) <= best_score else best


def normalize_public_value(value: Any) -> Any:
    """Normaliza recursivamente strings públicos sin mutar la entrada."""
    if isinstance(value, str):
        return repair_mojibake(value)
    if isinstance(value, Mapping):
        return {key: normalize_public_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_public_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(normalize_public_value(item) for item in value)
    return value


def dedupe_evidence(
    evidence: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplica evidencia por ref_id preservando orden y primera aparición."""
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in evidence:
        item = dict(raw)
        ref_id = str(item.get("ref_id") or "").strip()
        if ref_id:
            if ref_id in seen:
                continue
            seen.add(ref_id)
        result.append(item)
    return result


def normative_review_reason(
    *,
    has_material_evidence: bool,
    applicable_refs: Sequence[str],
    temporal_or_normative_review: bool,
) -> str | None:
    """Explica de forma determinista por qué el gate normativo exige revisión."""
    if temporal_or_normative_review:
        return (
            "La aplicabilidad normativa no pudo acreditarse completamente; "
            "se requiere revisión humana."
        )
    if has_material_evidence and not applicable_refs:
        return (
            "Existe evidencia normativa materialmente relacionada, pero ninguna "
            "referencia superó todos los gates de aplicabilidad; se requiere revisión humana."
        )
    return None
