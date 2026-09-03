from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_cbr_normative_citations import PrimaryCBRNormativeCitationLinkage
from app.domain.primary_cbr_problem_institution import PrimaryCBRProblemInstitutionClassification
from app.domain.primary_cbr_source_situations import PrimaryCBRSituationExtraction
from app.domain.primary_legal_knowledge import PrimaryKnowledgeManifest


class PrimaryCBRNormativeCitationError(RuntimeError):
    """Error controlado de vinculación de artículos citados CBR C.6."""


def load_primary_cbr_normative_citation_linkage(
    path: Path,
) -> PrimaryCBRNormativeCitationLinkage:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryCBRNormativeCitationError(
            f"No existe el recurso de artículos citados CBR C.6: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryCBRNormativeCitationLinkage.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryCBRNormativeCitationError(
            "El recurso de artículos citados CBR C.6 no es válido."
        ) from exc


def validate_primary_cbr_normative_citation_linkage(
    linkage: PrimaryCBRNormativeCitationLinkage,
    classification: PrimaryCBRProblemInstitutionClassification,
    prodecon: PrimaryCBRSituationExtraction,
    unam: PrimaryCBRSituationExtraction,
    manifest: PrimaryKnowledgeManifest,
) -> None:
    """Valida C.6 contra C.2/C.3/C.5 y A.8 sin ejecutar la validación C.7."""
    if linkage.baseline_commit != classification.baseline_commit:
        raise PrimaryCBRNormativeCitationError(
            "C.6 debe conservar el baseline CBR de C.1-C.5."
        )
    if linkage.primary_manifest_resource != "primary_legal_knowledge_manifest.json":
        raise PrimaryCBRNormativeCitationError("C.6 debe declarar el manifiesto A.8 usado.")

    source_items = {
        item.situation_id: item for item in [*prodecon.situations, *unam.situations]
    }
    classified = {item.situation_id: item for item in classification.classifications}
    linked = {item.situation_id: item for item in linkage.situations}

    if set(source_items) != set(classified) or set(linked) != set(classified):
        raise PrimaryCBRNormativeCitationError(
            "C.6 debe cubrir exactamente las 37 situaciones C.2/C.3 clasificadas en C.5."
        )
    if linkage.source_situation_count != classification.classified_situation_count:
        raise PrimaryCBRNormativeCitationError("C.6 perdió situaciones clasificadas C.5.")

    manifest_ids = set(manifest.normative_corpus_ids)
    if not set(linkage.candidate_corpus_ids) <= manifest_ids:
        raise PrimaryCBRNormativeCitationError(
            "C.6 sólo puede normalizar citas hacia los 12 corpus declarados en A.8."
        )

    global_link_ids: list[str] = []
    for situation_id, item in linked.items():
        previous = classified[situation_id]
        source = source_items[situation_id]

        if (
            item.source is not previous.source
            or item.source_entry_id != previous.source_entry_id
            or item.historical_regime_context != previous.historical_regime_context
        ):
            raise PrimaryCBRNormativeCitationError(
                f"C.6 perdió identidad C.5 en {situation_id}."
            )
        if (
            item.primary_problem_id != previous.primary_problem_id
            or item.primary_institution_id != previous.primary_institution_id
            or item.similarity_seed.model_dump() != previous.similarity_seed.model_dump()
            or item.unresolved_required_case_fields
            != previous.unresolved_required_case_fields
        ):
            raise PrimaryCBRNormativeCitationError(
                f"C.6 alteró clasificación o semilla CBR C.5 en {situation_id}."
            )

        source_pages = set(source.source_pages)
        for link in item.article_links:
            global_link_ids.append(link.link_id)
            if link.source_page not in source_pages:
                raise PrimaryCBRNormativeCitationError(
                    f"C.6 enlazó una cita fuera de las páginas fuente C.2/C.3: {link.link_id}."
                )
            if link.candidate_corpus_id not in manifest_ids:
                raise PrimaryCBRNormativeCitationError(
                    f"C.6 usa un corpus fuera de A.8: {link.link_id}."
                )
            if (
                link.article_presence_verified
                or link.article_content_verified
                or link.current_law_verified
            ):
                raise PrimaryCBRNormativeCitationError(
                    f"C.6 adelantó la validación C.7 en {link.link_id}."
                )

        if item.historical_regime_context and item.corpus_validated:
            raise PrimaryCBRNormativeCitationError(
                "C.6 no puede validar vigencia de un caso histórico."
            )

    if len(global_link_ids) != len(set(global_link_ids)):
        raise PrimaryCBRNormativeCitationError("C.6 no admite link_id globales duplicados.")

    if linkage.linked_situation_count != 25:
        raise PrimaryCBRNormativeCitationError("C.6 espera 25 situaciones con cita expresa.")
    if linkage.unlinked_situation_count != 12:
        raise PrimaryCBRNormativeCitationError("C.6 espera 12 situaciones sin cita expresa.")
    if linkage.article_link_count != 51:
        raise PrimaryCBRNormativeCitationError("C.6 espera 51 vínculos de artículo fuente.")
    if linkage.unique_candidate_normative_ref_count != 46:
        raise PrimaryCBRNormativeCitationError(
            "C.6 espera 46 referencias normativas candidatas únicas."
        )
    if linkage.candidate_corpus_ids != ["cff", "cpeum", "lfdc", "lisr", "liva"]:
        raise PrimaryCBRNormativeCitationError(
            "C.6 debe conservar el conjunto canónico de cinco corpus citados."
        )
    if linkage.verifies_article_presence or linkage.validates_current_law:
        raise PrimaryCBRNormativeCitationError("La verificación normativa corresponde a C.7.")
    if linkage.assigns_cbr_families or linkage.creates_operational_cases:
        raise PrimaryCBRNormativeCitationError("C.6 no puede adelantar C.8-C.10.")
    if linkage.modifies_existing_cbr_engine or linkage.can_control_legal_decision:
        raise PrimaryCBRNormativeCitationError("C.6 no debe modificar el motor CBR operativo.")
