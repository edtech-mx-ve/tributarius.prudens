from __future__ import annotations

from app.domain.integral_legal_analysis import IntegralLegalAnalysis
from app.domain.legal_fact_assessment import (
    LegalFactMateriality,
    LegalFactStatus,
)
from app.domain.query import ExtractedFact, FactOrigin, MissingField
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from app.services.legal_fact_assessment import assess_legal_facts
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


def _analysis() -> IntegralLegalAnalysis:
    result = _orchestrator(None).run(_request())
    return build_integral_legal_analysis(result)


def test_explicit_query_fact_is_supplied_not_accredited() -> None:
    analysis = _analysis()
    analysis.facts = [
        ExtractedFact(
            name="actividad",
            value="servicios profesionales",
            origin=FactOrigin.EXPLICIT,
        )
    ]
    analysis.missing_fields = []

    assessments = assess_legal_facts(analysis)

    assert len(assessments) == 1
    status = assessments[0].status
    assert status == LegalFactStatus.SUPPLIED
    assert assessments[0].evidence_refs == []


def test_inferred_fact_stays_inferred_and_is_not_promoted_to_accredited() -> None:
    analysis = _analysis()
    analysis.facts = [
        ExtractedFact(
            name="regimen_probable",
            value="actividad empresarial",
            origin=FactOrigin.INFERRED,
        )
    ]
    analysis.missing_fields = []

    assessments = assess_legal_facts(analysis)

    status = assessments[0].status
    assert status == LegalFactStatus.INFERRED
    assert assessments[0].origin == FactOrigin.INFERRED


def test_missing_requirement_becomes_material_missing_fact() -> None:
    analysis = _analysis()
    analysis.facts = []
    analysis.missing_fields = [
        MissingField(
            name="ejercicio_fiscal",
            reason="Se requiere para determinar la norma temporalmente aplicable.",
        )
    ]

    assessments = assess_legal_facts(analysis)

    assert len(assessments) == 1
    assert assessments[0].status == LegalFactStatus.MISSING
    assert assessments[0].materiality == LegalFactMateriality.MATERIAL
    assert assessments[0].requires_clarification is True


def test_existing_fact_is_not_duplicated_as_missing_by_name() -> None:
    analysis = _analysis()
    analysis.facts = [
        ExtractedFact(
            name="ejercicio_fiscal",
            value="2024",
            origin=FactOrigin.EXPLICIT,
        )
    ]
    analysis.missing_fields = [
        MissingField(
            name="ejercicio_fiscal",
            reason="Dato marcado como faltante por una etapa previa.",
        )
    ]

    assessments = assess_legal_facts(analysis)

    assert len(assessments) == 1
    assert assessments[0].status == LegalFactStatus.SUPPLIED


def test_fact_materiality_is_not_invented_for_extracted_facts() -> None:
    analysis = _analysis()
    analysis.facts = [
        ExtractedFact(
            name="dato_contextual",
            value="valor",
            origin=FactOrigin.EXPLICIT,
        )
    ]
    analysis.missing_fields = []

    assessments = assess_legal_facts(analysis)

    assert assessments[0].materiality == LegalFactMateriality.UNDETERMINED


def test_contract_supports_accredited_and_contested_without_auto_assigning_them() -> None:
    statuses = set(LegalFactStatus)

    assert LegalFactStatus.ACCREDITED in statuses
    assert LegalFactStatus.CONTESTED in statuses

    analysis = _analysis()
    assessments = assess_legal_facts(analysis)
    assert all(
        item.status not in {LegalFactStatus.ACCREDITED, LegalFactStatus.CONTESTED}
        for item in assessments
    )


def test_legal_decision_includes_structured_fact_assessment() -> None:
    analysis = _analysis()

    decision = build_legal_decision(analysis)

    assert decision.fact_assessments == assess_legal_facts(analysis)
    assert decision.conclusion == analysis.canonical_conclusion
    assert decision.controlling_source == analysis.controlling_source


def test_fact_assessment_cannot_change_legal_decision_conclusion() -> None:
    analysis = _analysis()
    expected_conclusion = analysis.canonical_conclusion
    analysis.facts.append(
        ExtractedFact(
            name="afirmacion_usuario",
            value="La autoridad actuó ilegalmente",
            origin=FactOrigin.EXPLICIT,
        )
    )

    decision = build_legal_decision(analysis)

    assert decision.conclusion == expected_conclusion
    assert decision.fact_assessments[-1].status == LegalFactStatus.SUPPLIED


def test_legal_decision_fact_assessments_are_defensive_copies() -> None:
    analysis = _analysis()

    decision = build_legal_decision(analysis)
    original = assess_legal_facts(analysis)

    if decision.fact_assessments:
        decision.fact_assessments[0].basis = "alterado"
        assert decision.fact_assessments != original
