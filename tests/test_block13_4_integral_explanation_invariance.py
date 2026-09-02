from __future__ import annotations

from datetime import UTC, datetime

from app.domain.explanation_mode import ExplanationMode
from app.domain.orchestration import HybridOrchestrationResult
from app.domain.traceability import CanonicalExecutionResult
from app.services.traceability import (
    build_canonical_result,
    verify_canonical_integrity,
)
from llm.models import ExplanationMode as LegacyExplanationMode
from tests.test_block12_4_hypothesis_verification import (
    _orchestrator,
    _request,
)

_NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _results_by_mode() -> dict[ExplanationMode, HybridOrchestrationResult]:
    orchestrator = _orchestrator(None)
    return {
        mode: orchestrator.run(
            _request().model_copy(update={"explanation_mode": mode})
        )
        for mode in ExplanationMode
    }


def _canonicals_by_mode() -> dict[ExplanationMode, CanonicalExecutionResult]:
    results = _results_by_mode()
    return {
        mode: build_canonical_result(
            _request().model_copy(update={"explanation_mode": mode}),
            result,
            now=_NOW,
        )
        for mode, result in results.items()
    }


def test_explanation_mode_enum_preserves_legacy_import_identity() -> None:
    assert LegacyExplanationMode is ExplanationMode


def test_three_modes_preserve_full_deterministic_orchestration_result() -> None:
    results = _results_by_mode()
    baseline = results[ExplanationMode.PROFESSIONAL]

    for mode, result in results.items():
        assert mode in ExplanationMode
        assert result.applicable_normative_refs == baseline.applicable_normative_refs
        assert result.rule_result == baseline.rule_result
        assert result.isr_result == baseline.isr_result
        assert result.hybrid_coordination == baseline.hybrid_coordination
        assert result.heuristic_evaluation == baseline.heuristic_evaluation
        assert result.requires_human_review == baseline.requires_human_review


def test_three_modes_preserve_traceability_legal_evidence_and_review() -> None:
    canonicals = _canonicals_by_mode()
    baseline = canonicals[ExplanationMode.PROFESSIONAL].traceability

    for canonical in canonicals.values():
        trace = canonical.traceability
        assert trace.evidence == baseline.evidence
        assert trace.jurisprudential_sources == baseline.jurisprudential_sources
        assert trace.hybrid_decision == baseline.hybrid_decision
        assert trace.uncertainties == baseline.uncertainties
        assert trace.requires_human_review == baseline.requires_human_review


def test_three_modes_preserve_canonical_legal_payload() -> None:
    canonicals = _canonicals_by_mode()
    baseline = canonicals[ExplanationMode.PROFESSIONAL]

    for canonical in canonicals.values():
        assert canonical.normative == baseline.normative
        assert canonical.rules == baseline.rules
        assert canonical.calculations == baseline.calculations
        assert canonical.cbr == baseline.cbr
        assert canonical.hybrid_coordination == baseline.hybrid_coordination
        assert canonical.uncertainty == baseline.uncertainty


def test_all_mode_canonical_results_keep_integrity() -> None:
    for canonical in _canonicals_by_mode().values():
        assert verify_canonical_integrity(canonical) is True


def test_explanation_stage_remains_after_deterministic_legal_stages_in_all_modes() -> None:
    results = _results_by_mode()

    for result in results.values():
        stages = [trace.stage.value for trace in result.traces]
        explanation_index = stages.index("explanation")

        assert stages.index("rules") < explanation_index
        assert stages.index("legal_heuristics") < explanation_index
        assert stages.index("legal_hypothesis_verification") < explanation_index


def test_mode_changes_never_promote_llm_to_controlling_source() -> None:
    results = _results_by_mode()

    for result in results.values():
        coordination = result.hybrid_coordination
        if coordination is None:
            assert result.cbr_result is None
            continue

        assert coordination.controlling_source != "llm"
        assert coordination.controlling_source != "explanation"
        assert coordination.controlling_source != "legal_hypothesis"


def test_block13_integral_contract_is_one_analysis_three_presentations() -> None:
    results = _results_by_mode()
    canonicals = _canonicals_by_mode()

    assert set(results) == {
        ExplanationMode.TAXPAYER,
        ExplanationMode.STUDENT,
        ExplanationMode.PROFESSIONAL,
    }

    legal_decisions = {
        (
            result.hybrid_coordination.conclusion
            if result.hybrid_coordination is not None
            else None,
            result.hybrid_coordination.controlling_source
            if result.hybrid_coordination is not None
            else None,
            result.requires_human_review,
        )
        for result in results.values()
    }
    assert len(legal_decisions) == 1

    evidence_sets = {
        tuple(item.ref_id for item in canonical.traceability.evidence)
        for canonical in canonicals.values()
    }
    assert len(evidence_sets) == 1
