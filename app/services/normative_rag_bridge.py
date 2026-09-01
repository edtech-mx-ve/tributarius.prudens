from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date
from enum import StrEnum

from app.domain.documents import SourceType
from app.domain.normative import (
    NormativeValidityBasis,
    NormativeValidityScope,
    NormativeValidityStatus,
)
from app.domain.orchestration import NormativeCandidate
from app.services.legal_unit_integrity import ArticleConsistency, compare_article_unit
from app.services.normative_temporal_runtime_guard import TemporalRuntimeGuard
from rag.retrieval.models import RetrievalHit, RetrievalResult


def _parse_enum[EnumT: StrEnum](
    value: str | None, enum_type: type[EnumT]
) -> EnumT | None:
    if not value:
        return None
    try:
        return enum_type(value)
    except ValueError:
        return None


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _unit_consistent(hit: RetrievalHit) -> bool:
    """Rechaza contradicciones explícitas entre etiqueta jurídica y texto."""
    metadata = hit.metadata
    label = metadata.source_unit_label or metadata.legal_identifier
    return (
        compare_article_unit(label, hit.text)
        != ArticleConsistency.MISMATCH
    )


def _stable_legal_unit_id(hit: RetrievalHit) -> int:
    identity = "|".join(
        (
            hit.metadata.document_id,
            hit.metadata.source_unit_label or "",
            hit.metadata.legal_identifier or "",
            hit.metadata.parent_chunk_id or hit.chunk_id,
        )
    )
    # Pydantic exige >0. Se limita a 63 bits para portabilidad SQL.
    value = int.from_bytes(
        hashlib.sha256(identity.encode("utf-8")).digest()[:8],
        "big",
    ) & ((1 << 63) - 1)
    return value or 1


def _ascii_fold(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in folded if not unicodedata.combining(char))


def _normalize_article_identifier(value: str) -> str | None:
    """Normaliza una etiqueta jurídica al identificador usado por reglas.

    Ejemplos:
    Artículo 110 -> articulo_110
    Artículo 1o. -> articulo_1
    Artículo 1o.-A -> articulo_1_a
    Artículo 6o Bis -> articulo_6_bis
    """
    clean = _ascii_fold(value)
    clean = clean.replace("º", "o").replace("°", "o")
    match = re.search(
        r"\bart(?:iculo|\.)?\s*([0-9]+)(?:o\.?)?(?:\s*[-.]?\s*([a-z]+))?",
        clean,
    )
    if match is None:
        match = re.search(r"\b([0-9]+)(?:o\.)?(?:\s*[-.]?\s*([a-z]+))?\b", clean)
    if match is None:
        return None

    number = match.group(1)
    suffix = match.group(2)
    if suffix:
        return f"articulo_{number}_{suffix}"
    return f"articulo_{number}"


def stable_legal_ref_from_hit(hit: RetrievalHit) -> str | None:
    """Obtiene identidad jurídica estable documento:unidad para el RBR."""
    metadata = hit.metadata
    if metadata.source_type != SourceType.NORMATIVA:
        return None

    legal_label = (
        metadata.source_unit_label
        or metadata.legal_identifier
        or metadata.hierarchy.article
    )
    if not legal_label:
        return None

    article_id = _normalize_article_identifier(legal_label)
    if article_id is None:
        return None

    document_id = metadata.document_id.strip().casefold()
    if not document_id:
        return None
    return f"{document_id}:{article_id}"


def build_rule_normative_refs(
    retrieval: RetrievalResult,
    applicable_chunk_refs: set[str],
) -> set[str]:
    """Expande solo normas ya declaradas aplicables a refs estables para RBR.

    Conserva los chunk_id para compatibilidad y agrega la identidad jurídica
    estable que usan las reglas de producción. Un hit recuperado pero no
    temporalmente aplicable nunca habilita por sí mismo una regla.
    """
    refs = set(applicable_chunk_refs)
    for hit in retrieval.hits:
        if hit.chunk_id not in applicable_chunk_refs:
            continue
        stable_ref = stable_legal_ref_from_hit(hit)
        if stable_ref is not None:
            refs.add(stable_ref)
    return refs


def candidate_from_normative_hit(
    hit: RetrievalHit,
    *,
    temporal_guard: TemporalRuntimeGuard | None = None,
) -> NormativeCandidate | None:
    """Promueve evidencia normativa válida de la base a candidato de razonamiento."""
    metadata = hit.metadata

    if metadata.source_type != SourceType.NORMATIVA:
        return None

    if not metadata.version_label:
        return None

    if not _unit_consistent(hit):
        return None

    legal_identifier = metadata.source_unit_label or metadata.legal_identifier
    verification = (
        temporal_guard.verification_for_document(
            metadata.document_id,
            legal_identifier=legal_identifier,
        )
        if temporal_guard is not None
        else None
    )

    effective_from = _parse_date(metadata.effective_from)
    effective_to = _parse_date(metadata.effective_to)
    validity_verified_at = _parse_date(metadata.validity_verified_at)
    validity_status = _parse_enum(metadata.validity_status, NormativeValidityStatus)
    validity_scope = _parse_enum(metadata.validity_scope, NormativeValidityScope)
    validity_basis = _parse_enum(metadata.validity_basis, NormativeValidityBasis)
    official_source = metadata.official_source

    # La evidencia temporal complementa la norma, pero no condiciona
    # su ingreso al razonamiento. La base normativa es conocimiento
    # fundacional utilizable aunque no exista verificación temporal.
    has_interval = effective_from is not None or effective_to is not None
    if not has_interval and verification is not None:
        validity_status = verification.validity_status
        validity_scope = verification.validity_scope
        validity_basis = verification.validity_basis
        validity_verified_at = verification.validity_verified_at
        official_source = verification.official_source

    return NormativeCandidate(
        ref=hit.chunk_id,
        legal_unit_id=_stable_legal_unit_id(hit),
        version_label=metadata.version_label,
        effective_from=effective_from,
        effective_to=effective_to,
        fiscal_year=metadata.fiscal_year,
        validity_status=(validity_status or NormativeValidityStatus.UNKNOWN),
        validity_scope=(validity_scope or NormativeValidityScope.UNKNOWN),
        validity_basis=(validity_basis or NormativeValidityBasis.UNKNOWN),
        validity_verified_at=validity_verified_at,
        official_source=official_source,
    )


def build_normative_candidates(
    retrieval: RetrievalResult,
    *,
    temporal_guard: TemporalRuntimeGuard | None = None,
) -> list[NormativeCandidate]:
    candidates: list[NormativeCandidate] = []
    seen: set[str] = set()
    for hit in retrieval.hits:
        candidate = candidate_from_normative_hit(
            hit,
            temporal_guard=temporal_guard,
        )
        if candidate is None or candidate.ref in seen:
            continue
        seen.add(candidate.ref)
        candidates.append(candidate)
    return candidates
