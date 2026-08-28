import json
from pathlib import Path

from app.domain.traceability import CanonicalExecutionResult
from app.web.presenter import present_canonical_result
from app.web.schemas import WebConsultationRequest


def load_fixture() -> CanonicalExecutionResult:
    payload = json.loads(
        Path("traceability/fixtures/trace_test.json").read_text(encoding="utf-8")
    )
    return CanonicalExecutionResult.model_validate(payload)


def test_presenter_exposes_trace_without_raw_query() -> None:
    result = present_canonical_result(
        load_fixture(),
        WebConsultationRequest(
            query="Consulta solo para la capa web",
            mode="professional",
            fiscal_year=2026,
        ),
    )
    assert result["folio"].startswith("TP-")
    assert result["mode"] == "professional"
    assert "query_analysis" not in result
    assert isinstance(result["evidence"], list)
    assert "calculations" in result
    assert "uncertainties" in result
