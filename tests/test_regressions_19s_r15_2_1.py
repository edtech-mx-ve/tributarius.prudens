from app.domain.query import QueryIntent
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


def _analyze(query: str):
    return QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(query)


def test_iva_rate_plus_legal_basis_is_interpretation() -> None:
    result = _analyze(
        "¿Cuál es la tasa general del IVA y cuál es su fundamento?"
    )
    assert result.primary_intent == QueryIntent.INTERPRET_PROVISION
    assert result.jurisprudence_requested is False


def test_generic_operational_iva_rate_is_calculation() -> None:
    result = _analyze(
        "Para 2026, ¿qué tasa de IVA debo aplicar a una operación gravada en México?"
    )
    assert result.primary_intent == QueryIntent.CALCULATE_IVA
    assert result.jurisprudence_requested is False
