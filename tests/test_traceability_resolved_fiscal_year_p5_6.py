from __future__ import annotations

from datetime import UTC, datetime

from app.domain.query import TemporalControlExecution
from app.services.traceability import build_canonical_result
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request

_NOW = datetime(2026, 9, 6, 6, 0, tzinfo=UTC)


def test_traceability_uses_resolved_fiscal_year_when_web_field_is_empty() -> None:
    base_request = _request()
    result = _orchestrator(None).run(base_request)

    temporal_execution = TemporalControlExecution.model_construct(
        resolved_query_fiscal_year=2026,
    )

    result = result.model_copy(
        update={"temporal_control_execution": temporal_execution}
    )
    request_without_explicit_year = base_request.model_copy(
        update={"query_fiscal_year": None}
    )

    canonical = build_canonical_result(
        request_without_explicit_year,
        result,
        now=_NOW,
    )

    assert canonical.traceability.query_fiscal_year == 2026


def test_traceability_preserves_request_year_without_temporal_execution() -> None:
    request = _request()
    result = _orchestrator(None).run(request).model_copy(
        update={"temporal_control_execution": None}
    )

    canonical = build_canonical_result(
        request,
        result,
        now=_NOW,
    )

    assert canonical.traceability.query_fiscal_year == 2026
