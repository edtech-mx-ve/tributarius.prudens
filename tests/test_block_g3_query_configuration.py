from __future__ import annotations

import pytest

from app.domain.explanation_mode import ExplanationMode
from app.services.legal_consultation_query_configuration import (
    LegalConsultationQueryConfigurationError,
    build_legal_consultation_query_configuration,
)
from app.web.schemas import WebConsultationRequest
from tests.test_block12_4_hypothesis_verification import _request
from tests.test_block_g1_legal_consultation_report import _components


def _inputs():
    canonical, _, _ = _components()
    orchestration = _request()
    web = WebConsultationRequest(
        query=orchestration.query,
        mode=orchestration.explanation_mode.value,
        fiscal_year=orchestration.query_fiscal_year,
    )
    return web, orchestration, canonical


def test_g3_preserves_query_and_effective_configuration() -> None:
    web, orchestration, canonical = _inputs()

    config = build_legal_consultation_query_configuration(
        web,
        orchestration,
        canonical,
    )

    assert config.query == web.query
    assert config.query_sha256 == canonical.traceability.query_sha256
    assert config.query_date == orchestration.query_date
    assert config.requested_fiscal_year == 2026
    assert config.resolved_fiscal_year == 2026
    assert config.explanation_mode is ExplanationMode.PROFESSIONAL
    assert config.top_k == 5
    assert config.session_jurisprudence_attached is False
    assert config.can_change_legal_decision is False


def test_g3_distinguishes_requested_from_resolved_fiscal_year() -> None:
    web, orchestration, canonical = _inputs()

    web = web.model_copy(update={"fiscal_year": None})
    orchestration = orchestration.model_copy(
        update={"query_fiscal_year": None}
    )

    config = build_legal_consultation_query_configuration(
        web,
        orchestration,
        canonical,
    )

    assert config.requested_fiscal_year is None
    assert config.resolved_fiscal_year == 2026


def test_g3_records_session_jurisprudence_without_interpreting_it() -> None:
    web, orchestration, canonical = _inputs()
    web = web.model_copy(
        update={"jurisprudence_session_id": "a" * 32}
    )

    config = build_legal_consultation_query_configuration(
        web,
        orchestration,
        canonical,
    )

    assert config.session_jurisprudence_attached is True


def test_g3_rejects_query_mismatch_between_web_and_orchestration() -> None:
    web, orchestration, canonical = _inputs()
    orchestration = orchestration.model_copy(
        update={"query": "Consulta distinta"}
    )

    with pytest.raises(
        LegalConsultationQueryConfigurationError,
        match="consultas distintas",
    ):
        build_legal_consultation_query_configuration(
            web,
            orchestration,
            canonical,
        )
