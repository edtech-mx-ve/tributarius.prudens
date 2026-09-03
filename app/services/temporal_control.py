from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, ValidationError

from app.domain.normative import NormativeDecision
from app.domain.query import (
    FocusedRAGPlan,
    FullCorpusExpansionPlan,
    MultidimensionalQueryAnalysis,
    NormativeRankingIntegration,
    QueryTemporalSignalKind,
    TemporalControlCandidateResult,
    TemporalControlExecution,
    TemporalControlPlan,
    TemporalYearResolution,
)
from app.services.normative_temporal_runtime_guard import TemporalRuntimeGuard
from rag.retrieval.models import RetrievalResult

if TYPE_CHECKING:
    from app.domain.orchestration import NormativeCandidate

_POLICY_PATH = (
    Path(__file__).resolve().parents[1] / "resources" / "temporal_control_policy.json"
)


class TemporalControlError(RuntimeError):
    """Error controlado del contrato temporal D.9."""


class _TemporalControlPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str
    source_block: str
    infer_single_explicit_year_as_fiscal_year: bool
    request_fiscal_year_has_precedence: bool
    conflict_when_request_year_not_in_query_years: bool
    ambiguous_when_multiple_query_years_without_request_year: bool
    fail_closed_on_query_temporal_conflict: bool
    fail_closed_on_query_temporal_ambiguity: bool
    fail_closed_unknown_validity: bool
    preserve_retrieved_normative_evidence: bool
    rule_promotion_requires_temporal_applicability: bool
    allow_temporally_non_applicable_as_evidence: bool
    temporal_guard_is_advisory_for_retrieval: bool
    temporal_guard_does_not_create_validity: bool


@dataclass(frozen=True)
class TemporalQueryResolution:
    requested_fiscal_year: int | None
    resolved_fiscal_year: int | None
    resolution: TemporalYearResolution
    conflict: bool
    ambiguity: bool
    blocks_promotion: bool


@lru_cache(maxsize=1)
def load_default_temporal_control_policy() -> _TemporalControlPolicy:
    try:
        payload = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
        policy = _TemporalControlPolicy.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise TemporalControlError("La política temporal D.9 no es válida.") from exc
    if policy.source_block != "D.9":
        raise TemporalControlError("La política temporal no pertenece al bloque D.9.")
    return policy


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _explicit_years(multidimensional: MultidimensionalQueryAnalysis) -> list[int]:
    years: list[int] = []
    for signal in multidimensional.temporal_signals:
        if signal.kind is not QueryTemporalSignalKind.EXPLICIT_YEAR:
            continue
        try:
            year = int(signal.value)
        except ValueError as exc:
            raise TemporalControlError(
                f"D.9 recibió un año explícito inválido: {signal.value}."
            ) from exc
        if year < 1900 or year > 2200:
            raise TemporalControlError(f"D.9 recibió un año fuera de rango: {year}.")
        years.append(year)
    return list(dict.fromkeys(years))


def build_temporal_control_plan(
    multidimensional: MultidimensionalQueryAnalysis,
    ranking: NormativeRankingIntegration,
    focused_plan: FocusedRAGPlan,
    expansion_plan: FullCorpusExpansionPlan,
) -> TemporalControlPlan:
    """Formaliza D.9 sin decidir vigencia antes de recuperar/evaluar la norma."""
    policy = load_default_temporal_control_policy()
    corpus_ids = list(ranking.normative_corpus_ids)
    if len(corpus_ids) != 12 or len(set(corpus_ids)) != 12:
        raise TemporalControlError("D.9 requiere exactamente los 12 corpus A.8.")
    if focused_plan.normative_corpus_ids != corpus_ids:
        raise TemporalControlError("D.7 y D.9 no conservan el mismo corpus A.8.")
    if expansion_plan.normative_corpus_ids != corpus_ids:
        raise TemporalControlError("D.8 y D.9 no conservan el mismo corpus A.8.")

    signal_kinds = [item.kind for item in multidimensional.temporal_signals]
    blocked_sources = _unique(
        [
            *focused_plan.temporal_blocked_source_ids,
            *expansion_plan.temporal_blocked_source_ids,
        ]
    )
    return TemporalControlPlan(
        plan_applied=True,
        explicit_query_years=_explicit_years(multidimensional),
        historical_context=(
            QueryTemporalSignalKind.HISTORICAL_CONTEXT in signal_kinds
        ),
        current_context=QueryTemporalSignalKind.CURRENT_CONTEXT in signal_kinds,
        vigency_requested=QueryTemporalSignalKind.VIGENCY_REQUEST in signal_kinds,
        temporal_blocked_source_ids=blocked_sources,
        normative_corpus_ids=corpus_ids,
        infer_single_explicit_year_as_fiscal_year=(
            policy.infer_single_explicit_year_as_fiscal_year
        ),
        fail_closed_unknown_validity=policy.fail_closed_unknown_validity,
        fail_closed_query_year_conflict=(
            policy.fail_closed_on_query_temporal_conflict
        ),
        fail_closed_query_year_ambiguity=(
            policy.fail_closed_on_query_temporal_ambiguity
        ),
        preserve_retrieved_normative_evidence=(
            policy.preserve_retrieved_normative_evidence
        ),
        rule_promotion_requires_temporal_applicability=(
            policy.rule_promotion_requires_temporal_applicability
        ),
        temporal_control_enabled=True,
        can_control_legal_decision=False,
    )


def resolve_temporal_query_context(
    plan: TemporalControlPlan,
    requested_fiscal_year: int | None,
) -> TemporalQueryResolution:
    """Resuelve el ejercicio sin inventar fechas exactas a partir de un año."""
    policy = load_default_temporal_control_policy()
    years = list(plan.explicit_query_years)

    if requested_fiscal_year is not None:
        conflict = bool(
            years
            and policy.conflict_when_request_year_not_in_query_years
            and requested_fiscal_year not in years
        )
        return TemporalQueryResolution(
            requested_fiscal_year=requested_fiscal_year,
            resolved_fiscal_year=requested_fiscal_year,
            resolution=(
                TemporalYearResolution.CONFLICT
                if conflict
                else TemporalYearResolution.REQUEST_FISCAL_YEAR
            ),
            conflict=conflict,
            ambiguity=False,
            blocks_promotion=(conflict and plan.fail_closed_query_year_conflict),
        )

    if len(years) == 1 and plan.infer_single_explicit_year_as_fiscal_year:
        return TemporalQueryResolution(
            requested_fiscal_year=None,
            resolved_fiscal_year=years[0],
            resolution=TemporalYearResolution.QUERY_EXPLICIT_YEAR,
            conflict=False,
            ambiguity=False,
            blocks_promotion=False,
        )

    if len(years) > 1 and policy.ambiguous_when_multiple_query_years_without_request_year:
        return TemporalQueryResolution(
            requested_fiscal_year=None,
            resolved_fiscal_year=None,
            resolution=TemporalYearResolution.AMBIGUOUS_QUERY_YEARS,
            conflict=False,
            ambiguity=True,
            blocks_promotion=plan.fail_closed_query_year_ambiguity,
        )

    return TemporalQueryResolution(
        requested_fiscal_year=None,
        resolved_fiscal_year=None,
        resolution=TemporalYearResolution.QUERY_DATE_ONLY,
        conflict=False,
        ambiguity=False,
        blocks_promotion=False,
    )


def _decision_refs(
    items: list[TemporalControlCandidateResult],
    decision: NormativeDecision,
) -> list[str]:
    return [item.ref for item in items if item.decision is decision]


def execute_temporal_control(
    *,
    plan: TemporalControlPlan,
    query_date: date,
    resolution: TemporalQueryResolution,
    retrieval: RetrievalResult,
    candidates: list[NormativeCandidate],
    normative_results: Sequence[object],
    evidence_refs: list[str],
    applicable_refs: list[str],
    temporal_guard: TemporalRuntimeGuard | None,
) -> TemporalControlExecution:
    """Aplica fail-closed D.9 sobre resultados del motor normativo existente."""
    from app.domain.normative import NormativeApplicabilityResult

    if not plan.plan_applied or not plan.temporal_control_enabled:
        raise TemporalControlError("D.9 requiere un plan temporal activo.")
    typed_results: list[NormativeApplicabilityResult] = []
    for item in normative_results:
        if not isinstance(item, NormativeApplicabilityResult):
            raise TemporalControlError("D.9 recibió un resultado normativo inválido.")
        typed_results.append(item)
    if len(candidates) != len(typed_results):
        raise TemporalControlError(
            "D.9 requiere correspondencia uno a uno entre candidatos y resultados."
        )

    hit_document_ids = {hit.chunk_id: hit.metadata.document_id for hit in retrieval.hits}
    evidence_set = set(evidence_refs)
    applicable_set = set(applicable_refs)
    candidate_items: list[TemporalControlCandidateResult] = []

    for candidate, result in zip(candidates, typed_results, strict=True):
        document_id = hit_document_ids.get(candidate.ref)
        guard_blocked = bool(
            document_id
            and (
                document_id in plan.temporal_blocked_source_ids
                or (
                    temporal_guard is not None
                    and temporal_guard.blocks_document(document_id)
                )
            )
        )
        applicable_by_engine = candidate.ref in applicable_set and result.applicable
        promotion_allowed = applicable_by_engine and not resolution.blocks_promotion
        if result.decision is NormativeDecision.UNKNOWN_VALIDITY and promotion_allowed:
            raise TemporalControlError(
                "D.9 detectó promoción incompatible con unknown_validity."
            )
        candidate_items.append(
            TemporalControlCandidateResult(
                ref=candidate.ref,
                document_id=document_id,
                decision=result.decision,
                applicable_by_normative_engine=applicable_by_engine,
                promoted_for_reasoning=promotion_allowed,
                evidence_preserved=candidate.ref in evidence_set,
                temporal_guard_document_blocked=guard_blocked,
                validity_status=result.validity_status,
                validity_scope=result.validity_scope,
                validity_basis=result.validity_basis,
                effective_from=result.effective_from,
                effective_to=result.effective_to,
                fiscal_year=result.fiscal_year,
                requires_human_review=result.requires_human_review,
            )
        )

    promoted_refs = [item.ref for item in candidate_items if item.promoted_for_reasoning]
    blocked_in_retrieval = _unique(
        [
            hit.metadata.document_id
            for hit in retrieval.hits
            if hit.metadata.document_id in plan.temporal_blocked_source_ids
            or (
                temporal_guard is not None
                and temporal_guard.blocks_document(hit.metadata.document_id)
            )
        ]
    )
    unresolved_refs = _unique(
        [
            *_decision_refs(candidate_items, NormativeDecision.UNKNOWN_VALIDITY),
            *_decision_refs(candidate_items, NormativeDecision.INVALID_DATA),
        ]
    )
    requires_review = bool(
        resolution.conflict
        or resolution.ambiguity
        or unresolved_refs
        or any(item.requires_human_review for item in candidate_items)
    )
    all_resolved = not unresolved_refs and not resolution.conflict and not resolution.ambiguity

    return TemporalControlExecution(
        control_completed=True,
        query_date=query_date,
        requested_query_fiscal_year=resolution.requested_fiscal_year,
        resolved_query_fiscal_year=resolution.resolved_fiscal_year,
        year_resolution=resolution.resolution,
        explicit_query_years=list(plan.explicit_query_years),
        query_temporal_conflict=resolution.conflict,
        query_temporal_ambiguity=resolution.ambiguity,
        candidate_count=len(candidates),
        applicable_count=sum(item.applicable_by_normative_engine for item in candidate_items),
        promoted_count=len(promoted_refs),
        evidence_refs=list(evidence_refs),
        promoted_normative_refs=promoted_refs,
        unknown_validity_refs=_decision_refs(
            candidate_items, NormativeDecision.UNKNOWN_VALIDITY
        ),
        expired_refs=_decision_refs(candidate_items, NormativeDecision.EXPIRED),
        not_yet_effective_refs=_decision_refs(
            candidate_items, NormativeDecision.NOT_YET_EFFECTIVE
        ),
        fiscal_year_mismatch_refs=_decision_refs(
            candidate_items, NormativeDecision.FISCAL_YEAR_MISMATCH
        ),
        invalid_data_refs=_decision_refs(candidate_items, NormativeDecision.INVALID_DATA),
        temporal_blocked_source_ids=list(plan.temporal_blocked_source_ids),
        blocked_source_ids_in_retrieval=blocked_in_retrieval,
        candidate_results=candidate_items,
        fail_closed_enforced=True,
        retrieved_evidence_preserved=True,
        rule_promotion_restricted_to_temporally_applicable=True,
        temporal_validation_completed=True,
        all_temporal_questions_resolved=all_resolved,
        requires_human_review=requires_review,
        can_control_legal_decision=False,
    )
