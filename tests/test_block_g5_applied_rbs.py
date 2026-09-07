from __future__ import annotations

import json

import pytest

from app.domain.hybrid_reasoning import ReasoningSource
from app.services.canonical_execution_snapshot import (
    build_canonical_execution_snapshot,
)
from app.services.legal_consultation_applied_rbs import (
    LegalConsultationAppliedRBSError,
    build_legal_consultation_applied_rbs,
)
from app.services.traceability import (
    build_canonical_result,
    verify_canonical_integrity,
)
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request
from tests.test_block_g1_legal_consultation_report import _NOW, _report


def _execution():
    request = _request()
    result = _orchestrator(None).run(request)
    canonical = build_canonical_result(
        request,
        result,
        now=_NOW,
    )
    return result, canonical


def test_g5_canonical_preserves_rule_evaluation_and_rbs_reasoning() -> None:
    result, canonical = _execution()

    assert result.rbs_reasoning is not None
    assert canonical.rules == result.rule_result.model_dump(mode="json")
    assert canonical.rbs_reasoning == (
        result.rbs_reasoning.model_dump(mode="json")
    )
    assert verify_canonical_integrity(canonical) is True


def test_g5_applied_rbs_preserves_actual_rule_identity_and_derivation() -> None:
    result, canonical = _execution()

    applied = build_legal_consultation_applied_rbs(
        result,
        canonical,
    )

    assert applied.normalized_reasoning.reasoning_source is ReasoningSource.RBS
    assert applied.rule_evaluation.matched_rules

    rule = applied.rule_evaluation.matched_rules[0]
    assert rule.rule_id == "ISR_RULE_001"
    assert rule.version == "1.0"
    assert rule.conclusion_code == "isr_profile"
    assert rule.normative_refs == ["NORM_TEST_ISR_2026"]

    assert applied.rule_evaluation.derivations
    derivation = applied.rule_evaluation.derivations[0]
    assert derivation.rule_id == rule.rule_id
    assert derivation.version == rule.version
    assert derivation.normative_refs == rule.normative_refs

    assert applied.determinative_role_preserved is True
    assert applied.source_result_reexecuted is False
    assert applied.can_create_second_legal_conclusion is False


def test_g5_report_contains_same_applied_rbs_without_second_conclusion() -> None:
    report = _report()

    assert report.applied_rbs.normalized_reasoning.reasoning_source is ReasoningSource.RBS
    assert (
        report.applied_rbs.normalized_reasoning.conclusion
        == report.analyzer.canonical_conclusion
    )
    assert report.applied_rbs.determinative_role_preserved is True
    assert report.applied_rbs.can_create_second_legal_conclusion is False


def test_g5_snapshot_preserves_normalized_rbs() -> None:
    _, canonical = _execution()

    snapshot = build_canonical_execution_snapshot(canonical)
    payload = json.loads(snapshot.canonical_json)

    assert canonical.rbs_reasoning is not None
    assert payload["rbs_reasoning"] == canonical.rbs_reasoning


def test_g5_rejects_divergent_canonical_rbs() -> None:
    result, canonical = _execution()

    tampered = canonical.model_copy(
        update={
            "rbs_reasoning": {
                "reasoning_source": "rbs",
                "conclusion": "Resultado alterado.",
            }
        }
    )

    with pytest.raises(
        LegalConsultationAppliedRBSError,
        match="divergencia",
    ):
        build_legal_consultation_applied_rbs(
            result,
            tampered,
        )
