from __future__ import annotations

from app.domain.query import (
    ExtractedFact,
    FactOrigin,
    QueryAnalysisDraft,
    QueryIntent,
)
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


def _facts(query: str) -> tuple[dict[str, str], object]:
    analysis = QueryAnalyzer(
        RuntimeQueryAnalyzerProvider()
    ).analyze(query)

    return (
        {
            fact.name: fact.value
            for fact in analysis.facts
        },
        analysis,
    )


def test_complete_monthly_isr_query_preserves_explicit_facts() -> None:
    query = (
        "Soy una persona fisica que presta servicios profesionales "
        "independientes en Mexico, bajo el regimen de actividades "
        "empresariales y profesionales. En septiembre de 2026 tuve "
        "una base gravable mensual de $35,000 MXN. Cuanto ISR me "
        "corresponde pagar por ese mes conforme a la tarifa "
        "aplicable de 2026?"
    )

    facts, analysis = _facts(query)

    assert analysis.primary_intent.value == "calculate_isr"

    assert facts["matter"] == "ISR"
    assert facts["taxpayer_type"] == "individual"
    assert facts["fiscal_year"] == "2026"
    assert facts["activity"] == (
        "servicios profesionales independientes"
    )
    assert facts["fiscal_regime"] == (
        "actividades empresariales y profesionales"
    )
    assert facts["isr_period"] == "monthly"
    assert facts["isr_month"] == "9"
    assert facts["taxable_base"] == "35000"
    assert facts["currency"] == "MXN"

    assert "gross_income" not in facts

    assert analysis.missing_fields == []
    assert analysis.requires_clarification is False


def test_incomplete_isr_query_keeps_base_but_requests_missing_context() -> None:
    query = (
        "Quiero calcular el ISR correspondiente a mis ingresos. "
        "Tuve una base gravable de $35,000 MXN y necesito saber "
        "cuanto impuesto corresponde."
    )

    facts, analysis = _facts(query)

    assert facts["matter"] == "ISR"
    assert facts["taxable_base"] == "35000"
    assert facts["currency"] == "MXN"

    assert "gross_income" not in facts

    missing = {
        item.name
        for item in analysis.missing_fields
    }

    assert missing == {
        "fiscal_year",
        "taxpayer_type",
        "isr_period",
    }

    assert analysis.requires_clarification is True


def test_isr_without_calculation_base_requests_it_explicitly() -> None:
    draft = QueryAnalysisDraft(
        primary_intent=QueryIntent.CALCULATE_ISR,
        facts=[
            ExtractedFact(
                name="taxpayer_type",
                value="individual",
                origin=FactOrigin.EXPLICIT,
            ),
            ExtractedFact(
                name="fiscal_year",
                value="2026",
                origin=FactOrigin.EXPLICIT,
            ),
            ExtractedFact(
                name="isr_period",
                value="monthly",
                origin=FactOrigin.EXPLICIT,
            ),
        ],
    )

    hardened = QueryAnalyzer._enforce_deterministic_requirements(
        draft
    )

    missing = {
        item.name
        for item in hardened.missing_fields
    }

    assert missing == {"taxable_base"}
    assert hardened.requires_clarification is True
