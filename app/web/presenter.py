from __future__ import annotations

from typing import Any

from app.domain.explanation_mode import ExplanationMode
from app.domain.hybrid_legal_decision import HybridLegalDecision
from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.domain.legal_decision import LegalDecision
from app.domain.traceability import CanonicalExecutionResult, EvidenceReference
from app.services.integral_legal_traceability import (
    integral_legal_analysis_sha256,
)
from app.services.legal_explanation_profile import get_legal_explanation_profile
from app.services.traceability import canonical_sha256
from app.web.schemas import WebConsultationRequest

_SNIPPET_LIMIT = 360


def _repair_mojibake(value: object) -> object:
    if not isinstance(value, str) or not any(mark in value for mark in ("Ã", "Â", "â")):
        return value
    try:
        repaired = value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value
    return repaired


def _safe_explanation(result: CanonicalExecutionResult) -> str | None:
    explanation = result.explanation
    if not isinstance(explanation, dict):
        return None
    answer = explanation.get("answer")
    if not isinstance(answer, dict):
        return None
    for key in ("summary", "analysis", "answer"):
        value = answer.get(key)
        if isinstance(value, str) and value.strip():
            return str(_repair_mojibake(value))
    return None


def _present_explanation_profile(mode: str) -> dict[str, object]:
    """Expone solo metadatos de presentación; nunca contenido jurídico."""

    profile = get_legal_explanation_profile(ExplanationMode(mode))
    return {
        "mode": profile.mode.value,
        "audience_label": profile.audience_label,
        "communication_goal": profile.communication_goal,
        "sections": list(profile.section_order),
        "style_instructions": list(profile.style_instructions),
    }


def _source_label(source_type: str | None) -> str:
    labels = {
        "normativa": "Normativa",
        "unam": "Doctrina UNAM",
        "prodecon": "Orientación PRODECON",
        "jurisprudencia": "Jurisprudencia",
    }
    return labels.get(source_type or "", "Otra evidencia")


def _evidence_role(item: EvidenceReference) -> str:
    if item.kind.value == "jurisprudence" or item.source_type == "jurisprudencia":
        return "jurisprudence"
    if item.source_type == "normativa" or item.kind.value == "normative":
        return "normative"
    if item.source_type in {"unam", "prodecon"}:
        return "supporting"
    return "other"


def _retrieval_details(result: CanonicalExecutionResult) -> dict[str, dict[str, Any]]:
    raw_hits = result.retrieval.get("hits", [])
    if not isinstance(raw_hits, list):
        return {}

    details: dict[str, dict[str, Any]] = {}
    for raw_hit in raw_hits:
        if not isinstance(raw_hit, dict):
            continue
        chunk_id = raw_hit.get("chunk_id")
        if not isinstance(chunk_id, str):
            continue
        metadata = raw_hit.get("metadata")
        metadata_dict = metadata if isinstance(metadata, dict) else {}
        text = raw_hit.get("text")
        snippet = ""
        if isinstance(text, str):
            normalized = " ".join(text.split())
            snippet = (
                normalized
                if len(normalized) <= _SNIPPET_LIMIT
                else f"{normalized[:_SNIPPET_LIMIT].rstrip()}…"
            )
        details[chunk_id] = {
            "document_id": metadata_dict.get("document_id"),
            "title": _repair_mojibake(metadata_dict.get("title")),
            "unit": _repair_mojibake(
                metadata_dict.get("source_unit_label")
                or metadata_dict.get("legal_identifier")
            ),
            "page_start": metadata_dict.get("page_start"),
            "page_end": metadata_dict.get("page_end"),
            "publication_date": metadata_dict.get("publication_date"),
            "effective_from": metadata_dict.get("effective_from"),
            "effective_to": metadata_dict.get("effective_to"),
            "snippet": _repair_mojibake(snippet),
        }
    return details


def _present_evidence(
    result: CanonicalExecutionResult,
) -> list[dict[str, object | None]]:
    retrieval = _retrieval_details(result)
    items: list[dict[str, object | None]] = []

    all_evidence = (
        list(result.traceability.evidence)
        + list(result.traceability.jurisprudential_sources)
    )
    seen_refs: set[str] = set()
    for item in all_evidence:
        if item.ref_id in seen_refs:
            continue
        seen_refs.add(item.ref_id)
        detail = retrieval.get(item.ref_id, {})
        items.append(
            {
                "ref_id": item.ref_id,
                "kind": item.kind.value,
                "role": _evidence_role(item),
                "source_type": item.source_type,
                "source_label": _source_label(item.source_type),
                "source_reference": item.source_reference,
                "version": item.version,
                "fiscal_year": item.fiscal_year,
                "score": item.score,
                "document_id": detail.get("document_id"),
                "title": detail.get("title"),
                "unit": detail.get("unit"),
                "page_start": detail.get("page_start"),
                "page_end": detail.get("page_end"),
                "publication_date": detail.get("publication_date"),
                "effective_from": detail.get("effective_from"),
                "effective_to": detail.get("effective_to"),
                "snippet": detail.get("snippet", ""),
            }
        )
    return items


def _present_hybrid_decision(result: CanonicalExecutionResult) -> dict[str, object] | None:
    decision = result.traceability.hybrid_decision
    if decision is None:
        return None
    return {
        "relation": decision.relation,
        "conclusion": decision.conclusion,
        "controlling_source": decision.controlling_source,
        "shared_legal_basis": list(decision.shared_legal_basis),
        "reasons": list(decision.reasons),
        "factors": dict(decision.factors),
        "rbs_trace": list(decision.rbs_trace),
        "cbr_trace": list(decision.cbr_trace),
        "requires_human_review": decision.requires_human_review,
    }


def _present_trace(result: CanonicalExecutionResult) -> dict[str, object]:
    trace = result.traceability
    return {
        "execution_id": trace.execution_id,
        "created_at_utc": trace.created_at_utc.isoformat(),
        "primary_intent": trace.primary_intent,
        "query_fiscal_year": trace.query_fiscal_year,
        "canonical_result_sha256": trace.canonical_result_sha256,
        "events": [
            {
                "sequence": event.sequence,
                "stage": event.stage,
                "status": event.status.value,
                "summary": event.summary,
                "evidence_refs": event.evidence_refs,
                "requires_human_review": event.requires_human_review,
            }
            for event in trace.events
        ],
    }


def present_integral_legal_analysis(
    analysis: IntegralLegalAnalysis,
) -> dict[str, object]:
    """Expone Analyzer 1.0 sin recalcular ni reinterpretar su contenido."""

    payload: dict[str, object] = analysis.model_dump(mode="json")
    payload["integrity_sha256"] = integral_legal_analysis_sha256(analysis)
    return payload


def present_legal_decision(
    decision: LegalDecision | HybridLegalDecision,
) -> dict[str, object]:
    """Expone Legal Decision 1.0/F.9 sin recalcular ni reinterpretar su contenido."""

    payload: dict[str, object] = decision.model_dump(mode="json")
    payload["integrity_sha256"] = canonical_sha256(payload)
    return payload


def present_canonical_result(
    result: CanonicalExecutionResult,
    request: WebConsultationRequest,
) -> dict[str, object]:
    """Proyección web: reduce el canónico sin recalcular ni reinterpretar."""
    evidence = _present_evidence(result)
    uncertainties = [
        item.model_dump(mode="json")
        for item in result.traceability.uncertainties
    ]
    return {
        "folio": result.folio,
        "mode": request.mode,
        "explanation_profile": _present_explanation_profile(request.mode),
        "requires_human_review": result.traceability.requires_human_review,
        "explanation": _safe_explanation(result),
        "applicable_normative_refs": result.normative.get(
            "applicable_refs",
            [],
        ),
        "calculations": result.calculations,
        "cbr": result.cbr,
        "evidence": evidence,
        "uncertainties": uncertainties,
        "hybrid_decision": _present_hybrid_decision(result),
        "traceability": _present_trace(result),
    }
