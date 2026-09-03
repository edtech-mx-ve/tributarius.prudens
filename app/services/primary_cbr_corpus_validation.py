from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.domain.primary_cbr_corpus_validation import PrimaryCBRCorpusValidationReport
from app.domain.primary_cbr_normative_citations import PrimaryCBRNormativeCitationLinkage


class PrimaryCBRCorpusValidationError(RuntimeError):
    """Error controlado de validación CBR C.7 contra corpus interno."""


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryCBRCorpusValidationError(f"No existe {label}: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrimaryCBRCorpusValidationError(f"No se pudo leer {label}.") from exc
    if not isinstance(payload, dict):
        raise PrimaryCBRCorpusValidationError(f"{label} debe ser un objeto JSON.")
    return payload


def _load_json_list(path: Path, *, label: str) -> list[dict[str, Any]]:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryCBRCorpusValidationError(f"No existe {label}: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PrimaryCBRCorpusValidationError(f"No se pudo leer {label}.") from exc
    if not isinstance(payload, list) or not all(isinstance(item, dict) for item in payload):
        raise PrimaryCBRCorpusValidationError(f"{label} debe ser una lista de objetos JSON.")
    return payload


def load_primary_cbr_corpus_validation_report(path: Path) -> PrimaryCBRCorpusValidationReport:
    payload = _load_json_object(path, label="el reporte C.7")
    try:
        return PrimaryCBRCorpusValidationReport.model_validate(payload)
    except ValidationError as exc:
        raise PrimaryCBRCorpusValidationError("El reporte C.7 no es válido.") from exc


def validate_primary_cbr_against_current_corpus(
    report: PrimaryCBRCorpusValidationReport,
    citation_linkage: PrimaryCBRNormativeCitationLinkage,
    *,
    primary_manifest_path: Path,
    fiscal_catalog_path: Path,
    temporal_registry_path: Path,
) -> None:
    """Contrasta C.7 con C.6, A.8, catálogo y registro temporal; nunca infiere vigencia."""
    manifest = _load_json_object(primary_manifest_path, label="el manifiesto A.8")
    catalog = _load_json_list(fiscal_catalog_path, label="el catálogo fiscal")
    temporal = _load_json_object(temporal_registry_path, label="el registro temporal")

    manifest_ids = manifest.get("normative_corpus_ids")
    if not isinstance(manifest_ids, list) or not all(
        isinstance(item, str) for item in manifest_ids
    ):
        raise PrimaryCBRCorpusValidationError("A.8 no expone normative_corpus_ids válidos.")
    if set(report.normative_corpus_ids) != set(manifest_ids):
        raise PrimaryCBRCorpusValidationError("C.7 debe usar exactamente los 12 corpus de A.8.")

    catalog_by_id = {
        str(item.get("canonical_id")): item
        for item in catalog
        if item.get("layer") == "normativa"
    }
    if not set(report.normative_corpus_ids) <= set(catalog_by_id):
        raise PrimaryCBRCorpusValidationError("Faltan fuentes C.7 en el catálogo fiscal interno.")

    snapshots = {item.canonical_id: item for item in report.corpus_snapshots}
    used_corpus_ids = {
        validation.candidate_corpus_id
        for situation in report.situations
        for validation in situation.article_validations
    }
    if set(snapshots) != used_corpus_ids:
        raise PrimaryCBRCorpusValidationError(
            "C.7 debe inventariar exactamente los corpus usados por C.6."
        )
    for canonical_id, snapshot in snapshots.items():
        catalog_item = catalog_by_id[canonical_id]
        if snapshot.filename != catalog_item.get("filename"):
            raise PrimaryCBRCorpusValidationError(
                f"{canonical_id} no coincide con el filename del catálogo interno."
            )
        if snapshot.title != catalog_item.get("title"):
            raise PrimaryCBRCorpusValidationError(
                f"{canonical_id} no coincide con el título del catálogo interno."
            )
        if snapshot.last_reform_date != catalog_item.get("last_reform_date"):
            raise PrimaryCBRCorpusValidationError(
                f"{canonical_id} altera la fecha de reforma registrada en el catálogo."
            )

    raw_gaps = temporal.get("coverage_gaps", [])
    if not isinstance(raw_gaps, list):
        raise PrimaryCBRCorpusValidationError("coverage_gaps temporal no es una lista.")
    blocked = {
        str(gap.get("canonical_id")).casefold()
        for gap in raw_gaps
        if isinstance(gap, dict)
        and gap.get("gap_type") == "document_wide_temporal_validity"
        and gap.get("status") == "unknown_fail_closed"
    }
    if set(report.document_wide_temporal_blocks) != blocked:
        raise PrimaryCBRCorpusValidationError(
            "C.7 no refleja los bloqueos temporales documentales vigentes."
        )
    if report.temporal_registry_source_sprint != temporal.get("source_sprint"):
        raise PrimaryCBRCorpusValidationError(
            "C.7 no corresponde al source_sprint temporal actual."
        )

    c6_by_id = {item.situation_id: item for item in citation_linkage.situations}
    c7_by_id = {item.situation_id: item for item in report.situations}
    if set(c7_by_id) != set(c6_by_id):
        raise PrimaryCBRCorpusValidationError(
            "C.7 debe procesar exactamente las 37 situaciones C.6."
        )

    for situation_id, c7 in c7_by_id.items():
        c6 = c6_by_id[situation_id]
        if (
            c7.source != c6.source
            or c7.source_entry_id != c6.source_entry_id
            or c7.historical_regime_context != c6.historical_regime_context
        ):
            raise PrimaryCBRCorpusValidationError(
                f"{situation_id} altera identidad o contexto heredado de C.6."
            )
        if c7.no_explicit_article_reason != c6.no_explicit_article_reason:
            raise PrimaryCBRCorpusValidationError(
                f"{situation_id} altera la razón de ausencia de cita C.6."
            )
        c6_links = {item.link_id: item for item in c6.article_links}
        c7_links = {item.link_id: item for item in c7.article_validations}
        if set(c7_links) != set(c6_links):
            raise PrimaryCBRCorpusValidationError(
                f"{situation_id} no valida exactamente los vínculos C.6."
            )
        for link_id, validation in c7_links.items():
            link = c6_links[link_id]
            if (
                validation.candidate_normative_ref != link.candidate_normative_ref
                or validation.candidate_corpus_id != link.candidate_corpus_id
                or validation.article != link.article
                or validation.qualifier != link.qualifier
            ):
                raise PrimaryCBRCorpusValidationError(
                    f"{link_id} altera corpus, artículo o calificador de C.6."
                )
            if validation.candidate_corpus_id not in report.normative_corpus_ids:
                raise PrimaryCBRCorpusValidationError(
                    f"{link_id} sale del corpus cerrado A.8."
                )
            expected_block = validation.candidate_corpus_id in blocked
            if validation.document_wide_temporal_block != expected_block:
                raise PrimaryCBRCorpusValidationError(
                    f"{link_id} no refleja correctamente el bloqueo temporal documental."
                )
            if validation.corpus_filename != snapshots[validation.candidate_corpus_id].filename:
                raise PrimaryCBRCorpusValidationError(
                    f"{link_id} no corresponde al snapshot normativo declarado."
                )
