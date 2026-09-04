from __future__ import annotations

from pathlib import Path

from app.domain.jurisprudence_benchmark import JurisprudenceBenchmarkScenario
from app.domain.jurisprudence_decision_application import (
    JurisprudenceCaseApplicationStatus,
    JurisprudenceDecisionEffect,
)
from app.domain.jurisprudence_evidence import JurisprudenceEvidenceDecision
from app.services.jurisprudence_benchmark import (
    load_jurisprudence_benchmark_suite,
    run_jurisprudence_benchmark,
    validate_jurisprudence_benchmark_suite,
)

ROOT = Path(__file__).resolve().parents[1]
SUITE_PATH = ROOT / "app" / "resources" / "jurisprudence_benchmark_suite.json"


def _report():
    return run_jurisprudence_benchmark(
        load_jurisprudence_benchmark_suite(SUITE_PATH)
    )


def test_e7_runs_all_eight_cases_at_perfect_threshold() -> None:
    report = _report()

    assert report.total_cases == 8
    assert report.passed_cases == 8
    assert report.pass_rate == 1.0
    assert report.threshold_met is True
    assert report.all_passed is True
    assert all(item.passed for item in report.results)


def test_e7_without_jurisprudence_preserves_optional_module_boundary() -> None:
    report = _report()
    case = next(
        item
        for item in report.results
        if item.scenario is JurisprudenceBenchmarkScenario.WITHOUT_JURISPRUDENCE
    )

    assert case.retrieved_count == 0
    assert case.authorized_evidence_count == 0
    assert case.evidence_decisions == []
    assert case.application_statuses == []
    assert case.binding_jurisprudence_applies is False
    assert case.requires_human_review is False
    assert report.optionality_contract_passed is True


def test_e7_bare_citation_never_becomes_binding_interpretation() -> None:
    report = _report()
    case = next(
        item
        for item in report.results
        if item.scenario is JurisprudenceBenchmarkScenario.CITATION_ONLY
    )

    assert case.evidence_decisions == [JurisprudenceEvidenceDecision.REVIEW_ONLY]
    assert case.authorized_evidence_count == 0
    assert case.binding_jurisprudence_applies is False


def test_e7_mandatory_but_materially_conflicting_ratio_does_not_apply() -> None:
    report = _report()
    case = next(
        item
        for item in report.results
        if item.scenario is JurisprudenceBenchmarkScenario.HARD_MATERIAL_CONFLICT
    )

    assert case.evidence_decisions == [JurisprudenceEvidenceDecision.ADMITTED]
    assert case.application_statuses == [
        JurisprudenceCaseApplicationStatus.NOT_APPLICABLE
    ]
    assert case.decision_effects == [JurisprudenceDecisionEffect.NO_EFFECT]
    assert case.binding_jurisprudence_applies is False


def test_e7_applicable_mandatory_ratio_governs_interpretation_only() -> None:
    report = _report()
    case = next(
        item
        for item in report.results
        if item.scenario is JurisprudenceBenchmarkScenario.MANDATORY_APPLICABLE
    )

    assert case.evidence_decisions == [JurisprudenceEvidenceDecision.ADMITTED]
    assert case.application_statuses == [JurisprudenceCaseApplicationStatus.APPLICABLE]
    assert case.decision_effects == [
        JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
    ]
    assert case.binding_jurisprudence_applies is True
    assert case.normative_basis_preserved is True
    assert case.single_conclusion_preserved is True


def test_e7_reference_2032043_passes_ratio_and_binding_contracts() -> None:
    report = _report()
    case = next(item for item in report.results if item.reference_thesis_2032043)

    assert case.scenario is JurisprudenceBenchmarkScenario.REFERENCE_2032043
    assert case.evidence_decisions == [JurisprudenceEvidenceDecision.ADMITTED]
    assert case.application_statuses == [JurisprudenceCaseApplicationStatus.APPLICABLE]
    assert case.decision_effects == [
        JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
    ]
    assert case.justification_ratio_boundary_preserved is True
    assert case.binding_jurisprudence_applies is True
    assert report.reference_thesis_2032043_passed is True


def test_e7_preserves_all_global_jurisprudence_boundaries() -> None:
    suite = load_jurisprudence_benchmark_suite(SUITE_PATH)
    validate_jurisprudence_benchmark_suite(suite)
    report = run_jurisprudence_benchmark(suite)

    assert report.session_scope_contract_passed is True
    assert report.ratio_justification_contract_passed is True
    assert report.normative_basis_contract_passed is True
    assert report.single_conclusion_contract_passed is True
    assert suite.jurisprudence_is_optional is True
    assert suite.session_scope_required is True
    assert suite.justification_is_ratio_source is True
    assert suite.thematic_similarity_can_establish_applicability is False
    assert suite.jurisprudence_can_replace_normative_basis is False
    assert suite.jurisprudence_can_create_second_conclusion is False
    assert suite.allows_web_jurisprudence is False


def test_e7_is_reproducible_and_scoped_to_current_dataset() -> None:
    suite = load_jurisprudence_benchmark_suite(SUITE_PATH)
    first = run_jurisprudence_benchmark(suite)
    second = run_jurisprudence_benchmark(suite)

    assert first == second
    assert suite.baseline_commit == "57c3fa580d88f148b498566d90c872bb59b26860"
    assert suite.validates_current_dataset_only is True
    assert suite.claims_full_mexican_jurisprudence_coverage is False
    assert first.validates_current_dataset_only is True
    assert first.claims_full_mexican_jurisprudence_coverage is False
