from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from app.domain.normative import (
    NormativeValidityBasis,
    NormativeValidityScope,
    NormativeValidityStatus,
)


class TemporalRuntimeGuardError(RuntimeError):
    """Error controlado al cargar la política temporal de runtime."""


@dataclass(frozen=True)
class TemporalValidityVerification:
    """Verificación explícita de vigencia sin convertir otras fechas en vigencia."""

    canonical_id: str
    legal_identifier: str | None
    validity_status: NormativeValidityStatus
    validity_scope: NormativeValidityScope
    validity_basis: NormativeValidityBasis
    validity_verified_at: date
    official_source: str
    reason: str


@dataclass(frozen=True)
class TemporalRuntimeGuard:
    """Bloquea promoción normativa cuando la vigencia documental sigue desconocida."""

    blocked_documents: frozenset[str]
    schema_version: str
    source_sprint: str
    verified_validity: tuple[TemporalValidityVerification, ...] = ()

    def blocks_document(self, document_id: str) -> bool:
        return document_id.casefold() in self.blocked_documents

    def verification_for_document(
        self,
        document_id: str,
        legal_identifier: str | None = None,
    ) -> TemporalValidityVerification | None:
        normalized_document = document_id.casefold()
        normalized_unit = _normalize_legal_identifier(legal_identifier)

        if normalized_unit is not None:
            legal_unit_match = next(
                (
                    item
                    for item in self.verified_validity
                    if item.canonical_id == normalized_document
                    and item.validity_scope is NormativeValidityScope.LEGAL_UNIT
                    and _normalize_legal_identifier(item.legal_identifier)
                    == normalized_unit
                ),
                None,
            )
            if legal_unit_match is not None:
                return legal_unit_match

        return next(
            (
                item
                for item in self.verified_validity
                if item.canonical_id == normalized_document
                and item.validity_scope is NormativeValidityScope.DOCUMENT
            ),
            None,
        )


def _normalize_legal_identifier(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split()).casefold()
    return normalized or None


def _as_dict(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TemporalRuntimeGuardError(f"{label} debe ser un objeto JSON.")
    return value


def _as_list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise TemporalRuntimeGuardError(f"{label} debe ser una lista JSON.")
    return value


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise TemporalRuntimeGuardError(f"Campo requerido inválido: {key}.")
    return value.strip()


def _required_date(data: dict[str, Any], key: str) -> date:
    raw = _required_str(data, key)
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise TemporalRuntimeGuardError(
            f"Campo de fecha inválido: {key}."
        ) from exc


def _load_verification(raw: object) -> TemporalValidityVerification:
    item = _as_dict(raw, label="verified_validity")
    try:
        status = NormativeValidityStatus(_required_str(item, "validity_status"))
        scope = NormativeValidityScope(_required_str(item, "validity_scope"))
        basis = NormativeValidityBasis(_required_str(item, "validity_basis"))
    except ValueError as exc:
        raise TemporalRuntimeGuardError(
            "verified_validity contiene un enum temporal desconocido."
        ) from exc

    if status is not NormativeValidityStatus.VERIFIED_IN_FORCE:
        raise TemporalRuntimeGuardError(
            "Una verificación sin intervalo solo puede declarar verified_in_force."
        )
    if scope not in {
        NormativeValidityScope.DOCUMENT,
        NormativeValidityScope.LEGAL_UNIT,
    }:
        raise TemporalRuntimeGuardError(
            "La verificación debe tener alcance document o legal_unit."
        )
    if basis not in {
        NormativeValidityBasis.OFFICIAL_CONSOLIDATED_VERSION,
        NormativeValidityBasis.VERIFIED_REFORM_CHAIN,
    }:
        raise TemporalRuntimeGuardError(
            "La verificación requiere fuente consolidada oficial o cadena de reformas."
        )

    legal_identifier_raw = item.get("legal_identifier")
    if legal_identifier_raw is not None and not isinstance(legal_identifier_raw, str):
        raise TemporalRuntimeGuardError(
            "legal_identifier debe ser texto cuando se proporciona."
        )
    legal_identifier = (
        legal_identifier_raw.strip()
        if isinstance(legal_identifier_raw, str) and legal_identifier_raw.strip()
        else None
    )
    if scope is NormativeValidityScope.LEGAL_UNIT and legal_identifier is None:
        raise TemporalRuntimeGuardError(
            "Una verificación legal_unit requiere legal_identifier."
        )
    if scope is NormativeValidityScope.DOCUMENT and legal_identifier is not None:
        raise TemporalRuntimeGuardError(
            "Una verificación document no debe declarar legal_identifier."
        )

    return TemporalValidityVerification(
        canonical_id=_required_str(item, "canonical_id").casefold(),
        legal_identifier=legal_identifier,
        validity_status=status,
        validity_scope=scope,
        validity_basis=basis,
        validity_verified_at=_required_date(item, "validity_verified_at"),
        official_source=_required_str(item, "official_source"),
        reason=_required_str(item, "reason"),
    )


def load_temporal_runtime_guard(path: Path) -> TemporalRuntimeGuard:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise TemporalRuntimeGuardError(
            f"No existe registro temporal de procedencia: {resolved}"
        )

    try:
        payload = _as_dict(
            json.loads(resolved.read_text(encoding="utf-8")),
            label="registro temporal",
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TemporalRuntimeGuardError(
            f"No se pudo leer el registro temporal: {resolved}"
        ) from exc

    schema_version = _required_str(payload, "schema_version")
    source_sprint = _required_str(payload, "source_sprint")
    gaps = _as_list(payload.get("coverage_gaps"), label="coverage_gaps")
    verified_raw = _as_list(
        payload.get("verified_validity", []),
        label="verified_validity",
    )

    blocked: set[str] = set()
    for raw_gap in gaps:
        gap = _as_dict(raw_gap, label="coverage_gap")
        canonical_id = _required_str(gap, "canonical_id").casefold()
        gap_type = _required_str(gap, "gap_type")
        status = _required_str(gap, "status")
        if (
            gap_type == "document_wide_temporal_validity"
            and status == "unknown_fail_closed"
        ):
            blocked.add(canonical_id)

    verified = tuple(_load_verification(item) for item in verified_raw)
    verified_keys = [
        (
            item.canonical_id,
            item.validity_scope.value,
            _normalize_legal_identifier(item.legal_identifier),
        )
        for item in verified
    ]
    if len(verified_keys) != len(set(verified_keys)):
        raise TemporalRuntimeGuardError(
            "verified_validity contiene verificaciones duplicadas por alcance."
        )

    verified_documents = {
        item.canonical_id
        for item in verified
        if item.validity_scope is NormativeValidityScope.DOCUMENT
    }
    overlap = blocked.intersection(verified_documents)
    if overlap:
        raise TemporalRuntimeGuardError(
            "Un documento no puede estar simultáneamente bloqueado y verificado: "
            + ", ".join(sorted(overlap))
        )

    return TemporalRuntimeGuard(
        blocked_documents=frozenset(blocked),
        schema_version=schema_version,
        source_sprint=source_sprint,
        verified_validity=verified,
    )
