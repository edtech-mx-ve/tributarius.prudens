from app.domain.query import QueryAnalysis, QueryIntent
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


def _analyze(query: str) -> QueryAnalysis:
    return QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(query)


def test_iva_rate_and_legal_basis_is_interpretation_not_jurisprudence() -> None:
    result = _analyze(
        "¿Cuál es la tasa general del IVA y cuál es su fundamento?"
    )

    assert result.primary_intent == QueryIntent.INTERPRET_PROVISION
    assert result.jurisprudence_requested is False
    assert result.requires_clarification is False
    assert any(
        fact.name == "matter" and fact.value == "IVA"
        for fact in result.facts
    )


def test_jurisprudence_requires_explicit_jurisprudential_language() -> None:
    result = _analyze(
        "¿Existe jurisprudencia relacionada con la interpretación del IVA?"
    )

    assert result.primary_intent == QueryIntent.RELATED_JURISPRUDENCE
    assert result.jurisprudence_requested is True


def test_iva_calculation_keeps_calculation_intent() -> None:
    result = _analyze("Quiero calcular el IVA de una operación.")

    assert result.primary_intent == QueryIntent.CALCULATE_IVA
    assert result.jurisprudence_requested is False


def test_generic_tax_query_does_not_activate_jurisprudence() -> None:
    result = _analyze("Explícame el IVA.")

    assert result.primary_intent in {
        QueryIntent.LEARN_TAX_LAW,
        QueryIntent.UNDERSTAND_TAX_SYSTEM,
    }
    assert result.jurisprudence_requested is False


def test_prompt_metadata_does_not_leak_intent_keywords_into_query() -> None:
    result = _analyze("Necesito orientación general sobre mis impuestos.")

    assert result.primary_intent == QueryIntent.UNDERSTAND_TAX_SYSTEM
    assert result.jurisprudence_requested is False
