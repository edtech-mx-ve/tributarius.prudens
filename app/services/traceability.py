from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from app.domain.orchestration import HybridOrchestrationRequest, HybridOrchestrationResult
from app.domain.traceability import (
    CanonicalExecutionResult,
    EvidenceKind,
    EvidenceReference,
    TraceabilityRecord,
    TraceEvent,
    TraceEventStatus,
    UncertaintyItem,
)


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_sha256(payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return sha256_text(serialized)


def create_execution_identity(
    now: datetime | None = None,
) -> tuple[str, str, datetime]:
    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    timestamp = timestamp.astimezone(UTC)
    token = uuid.uuid4().hex.upper()
    execution_id = f"TP-{token}"
    folio = f"TP-{timestamp:%Y%m%d}-{token[:12]}"
    return execution_id, folio, timestamp


def _event_status(value: str, review: bool) -> TraceEventStatus:
    if review:
        return TraceEventStatus.REVIEW_REQUIRED
    return TraceEventStatus(value)


def _stage_review(
    stage: str,
    result: HybridOrchestrationResult,
) -> bool:
    if stage == "query_analysis":
        return result.analysis.requires_human_review
    if stage == "normative":
        return any(item.requires_human_review for item in result.normative_results)
    if stage == "jurisprudence":
        return (
            result.jurisprudence_result.requires_human_review
            if result.jurisprudence_result is not None
            else False
        )
    if stage == "rules":
        return result.rule_result.requires_human_review
    if stage == "cbr":
        return any(
            item.requires_human_review
            for item in result.cbr_reuse_assessments
        )
    if stage == "explanation":
        return (
            result.explanation.answer.requires_human_review
            if result.explanation is not None
            else result.requires_human_review
        )
    return False


def _stage_evidence_refs(
    stage: str,
    result: HybridOrchestrationResult,
) -> list[str]:
    if stage == "retrieval":
        return [item.chunk_id for item in result.retrieval.hits]
    if stage == "normative":
        return list(result.applicable_normative_refs)
    if stage == "jurisprudence" and result.jurisprudence_result is not None:
        return [item.chunk_id for item in result.jurisprudence_result.hits]
    if stage == "rules":
        return [
            f"{item.rule_id}@{item.version}"
            for item in result.rule_result.matched_rules
        ]
    if stage == "isr" and result.isr_result is not None:
        return [f"ISR@{result.isr_result.tariff_version}"]
    if stage == "cbr" and result.cbr_result is not None:
        return [item.case_id for item in result.cbr_result.matches]
    if stage == "explanation" and result.explanation is not None:
        return list(result.explanation.answer.evidence_ids)
    return []


def _build_events(result: HybridOrchestrationResult) -> list[TraceEvent]:
    events: list[TraceEvent] = []
    for sequence, trace in enumerate(result.traces, start=1):
        review = _stage_review(trace.stage.value, result)
        events.append(
            TraceEvent(
                sequence=sequence,
                stage=trace.stage.value,
                status=_event_status(trace.status.value, review),
                summary=trace.detail,
                evidence_refs=_stage_evidence_refs(trace.stage.value, result),
                requires_human_review=review,
            )
        )
    return events

def _retrieval_evidence(
    result: HybridOrchestrationResult,
) -> list[EvidenceReference]:
    refs: list[EvidenceReference] = []
    for hit in result.retrieval.hits:
        refs.append(
            EvidenceReference(
                ref_id=hit.chunk_id,
                kind=EvidenceKind.DOCUMENT,
                source_type=hit.metadata.source_type.value,
                source_reference=hit.metadata.source_filename,
                version=hit.metadata.version_label,
                fiscal_year=hit.metadata.fiscal_year,
                score=hit.score,
            )
        )
    return refs


def _normative_evidence(
    request: HybridOrchestrationRequest,
    result: HybridOrchestrationResult,
) -> list[EvidenceReference]:
    by_identity = {
        (candidate.legal_unit_id, candidate.version_label): candidate
        for candidate in request.normative_candidates
    }
    refs: list[EvidenceReference] = []
    for item in result.normative_results:
        candidate = by_identity.get((item.legal_unit_id, item.version_label))
        if candidate is None:
            continue
        refs.append(
            EvidenceReference(
                ref_id=candidate.ref,
                kind=EvidenceKind.NORMATIVE,
                version=item.version_label,
                fiscal_year=item.fiscal_year,
            )
        )
    return refs


def _rule_evidence(result: HybridOrchestrationResult) -> list[EvidenceReference]:
    return [
        EvidenceReference(
            ref_id=f"{item.rule_id}@{item.version}",
            kind=EvidenceKind.RULE,
            version=item.version,
        )
        for item in result.rule_result.matched_rules
    ]


def _calculation_evidence(
    result: HybridOrchestrationResult,
) -> list[EvidenceReference]:
    if result.isr_result is None:
        return []
    return [
        EvidenceReference(
            ref_id=f"ISR@{result.isr_result.tariff_version}",
            kind=EvidenceKind.CALCULATION,
            source_reference=result.isr_result.source_reference,
            version=result.isr_result.tariff_version,
            fiscal_year=result.isr_result.fiscal_year,
        )
    ]


def _cbr_evidence(result: HybridOrchestrationResult) -> list[EvidenceReference]:
    if result.cbr_result is None:
        return []
    return [
        EvidenceReference(
            ref_id=item.case_id,
            kind=EvidenceKind.CBR_CASE,
            source_reference=";".join(item.source_refs),
            score=item.similarity,
        )
        for item in result.cbr_result.matches
    ]


def _jurisprudence_evidence(
    result: HybridOrchestrationResult,
) -> list[EvidenceReference]:
    if result.jurisprudence_result is None:
        return []
    return [
        EvidenceReference(
            ref_id=hit.chunk_id,
            kind=EvidenceKind.JURISPRUDENCE,
            source_type="jurisprudencia",
            source_reference=hit.metadata.source_reference,
            version=hit.metadata.status.value,
            score=hit.score,
        )
        for hit in result.jurisprudence_result.hits
    ]


def _llm_evidence(result: HybridOrchestrationResult) -> list[EvidenceReference]:
    if result.explanation is None:
        return []
    return [
        EvidenceReference(
            ref_id=(
                f"{result.explanation.provider_name}:"
                f"{result.explanation.model_name}"
            ),
            kind=EvidenceKind.LLM_EXPLANATION,
            source_reference=result.explanation.provider_name,
            version=result.explanation.model_name,
        )
    ]


def _uncertainties(
    result: HybridOrchestrationResult,
) -> list[UncertaintyItem]:
    items: list[UncertaintyItem] = []
    for missing in result.analysis.missing_fields:
        items.append(
            UncertaintyItem(
                code="MISSING_FIELD",
                message=f"{missing.name}: {missing.reason}",
                stage="query_analysis",
                requires_human_review=result.analysis.requires_human_review,
            )
        )
    for ambiguity in result.analysis.ambiguities:
        items.append(
            UncertaintyItem(
                code="QUERY_AMBIGUITY",
                message=ambiguity,
                stage="query_analysis",
                requires_human_review=result.analysis.requires_human_review,
            )
        )
    for norm in result.normative_results:
        if not norm.applicable:
            items.append(
                UncertaintyItem(
                    code=f"NORM_{norm.decision.value.upper()}",
                    message=norm.reason,
                    stage="normative",
                    requires_human_review=norm.requires_human_review,
                )
            )
    if result.jurisprudence_result is not None:
        for hit in result.jurisprudence_result.hits:
            if hit.assessment.requires_human_review:
                items.append(
                    UncertaintyItem(
                        code="JURISPRUDENCE_REVIEW",
                        message=(
                            f"{hit.metadata.identifier}: "
                            f"{', '.join(hit.assessment.reasons)}"
                        ),
                        stage="jurisprudence",
                        requires_human_review=True,
                    )
                )
    for assessment in result.cbr_reuse_assessments:
        if assessment.requires_human_review:
            items.append(
                UncertaintyItem(
                    code="CBR_REUSE_REVIEW",
                    message=f"{assessment.case_id}: {assessment.reason}",
                    stage="cbr",
                    requires_human_review=True,
                )
            )
    if result.explanation is None:
        items.append(
            UncertaintyItem(
                code="EXPLANATION_UNAVAILABLE",
                message="No se produjo explicación LLM.",
                stage="explanation",
                requires_human_review=result.requires_human_review,
            )
        )
    return items


def build_traceability_record(
    request: HybridOrchestrationRequest,
    result: HybridOrchestrationResult,
    *,
    execution_id: str,
    folio: str,
    created_at_utc: datetime,
) -> TraceabilityRecord:
    evidence = (
        _retrieval_evidence(result)
        + _normative_evidence(request, result)
        + _rule_evidence(result)
        + _calculation_evidence(result)
        + _cbr_evidence(result)
        + _llm_evidence(result)
    )
    return TraceabilityRecord(
        execution_id=execution_id,
        folio=folio,
        created_at_utc=created_at_utc,
        query_sha256=sha256_text(request.query),
        primary_intent=result.analysis.primary_intent.value,
        query_fiscal_year=request.query_fiscal_year,
        events=_build_events(result),
        evidence=evidence,
        jurisprudential_sources=_jurisprudence_evidence(result),
        uncertainties=_uncertainties(result),
        requires_human_review=result.requires_human_review,
    )


def build_canonical_result(
    request: HybridOrchestrationRequest,
    result: HybridOrchestrationResult,
    *,
    now: datetime | None = None,
) -> CanonicalExecutionResult:
    execution_id, folio, created_at = create_execution_identity(now)
    trace = build_traceability_record(
        request,
        result,
        execution_id=execution_id,
        folio=folio,
        created_at_utc=created_at,
    )
    payload: dict[str, Any] = {
        "query_analysis": result.analysis.model_dump(mode="json"),
        "retrieval": result.retrieval.model_dump(mode="json"),
        "normative": {
            "results": [
                item.model_dump(mode="json")
                for item in result.normative_results
            ],
            "applicable_refs": result.applicable_normative_refs,
        },
        "rules": result.rule_result.model_dump(mode="json"),
        "calculations": {
            "isr": (
                result.isr_result.model_dump(mode="json")
                if result.isr_result is not None
                else None
            )
        },
        "cbr": {
            "retrieval": (
                result.cbr_result.model_dump(mode="json")
                if result.cbr_result is not None
                else None
            ),
            "reuse_assessments": [
                item.model_dump(mode="json")
                for item in result.cbr_reuse_assessments
            ],
        },
        "explanation": (
            result.explanation.model_dump(mode="json")
            if result.explanation is not None
            else None
        ),
        "uncertainty": {
            "requires_human_review": result.requires_human_review,
            "items": [
                item.model_dump(mode="json")
                for item in trace.uncertainties
            ],
        },
    }
    if result.jurisprudence_result is not None:
        payload["jurisprudence"] = result.jurisprudence_result.model_dump(mode="json")
    trace.canonical_result_sha256 = canonical_sha256(payload)
    return CanonicalExecutionResult(
        execution_id=execution_id,
        folio=folio,
        created_at_utc=created_at,
        query_analysis=payload["query_analysis"],
        retrieval=payload["retrieval"],
        normative=payload["normative"],
        jurisprudence=payload.get("jurisprudence"),
        rules=payload["rules"],
        calculations=payload["calculations"],
        cbr=payload["cbr"],
        explanation=payload["explanation"],
        uncertainty=payload["uncertainty"],
        traceability=trace,
    )


def verify_canonical_integrity(result: CanonicalExecutionResult) -> bool:
    payload: dict[str, Any] = {
        "query_analysis": result.query_analysis,
        "retrieval": result.retrieval,
        "normative": result.normative,
        "rules": result.rules,
        "calculations": result.calculations,
        "cbr": result.cbr,
        "explanation": result.explanation,
        "uncertainty": result.uncertainty,
    }
    if result.jurisprudence is not None:
        payload["jurisprudence"] = result.jurisprudence
    expected = result.traceability.canonical_result_sha256
    return expected is not None and canonical_sha256(payload) == expected


def verify_query_fingerprint(
    query: str,
    trace: TraceabilityRecord,
) -> bool:
    return sha256_text(query) == trace.query_sha256
