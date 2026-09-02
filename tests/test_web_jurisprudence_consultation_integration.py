from pathlib import Path

import pytest
from pydantic import ValidationError

from app.web.runtime_runner import _explanation_mode
from app.web.schemas import WebConsultationRequest
from llm.models import ExplanationMode


def test_web_request_accepts_jurisprudence_session_id() -> None:
    request = WebConsultationRequest(
        query="¿Procede la devolución?",
        mode="professional",
        jurisprudence_session_id="a" * 32,
    )

    assert request.jurisprudence_session_id == "a" * 32


def test_web_rejects_invalid_jurisprudence_session_id() -> None:
    with pytest.raises(ValidationError):
        WebConsultationRequest(
            query="¿Procede la devolución?",
            jurisprudence_session_id="../escape",
        )


def test_llama_mode_is_forwarded_from_web_contract() -> None:
    assert _explanation_mode("student") is ExplanationMode.STUDENT
    assert _explanation_mode("professional") is ExplanationMode.PROFESSIONAL
    assert _explanation_mode("taxpayer") is ExplanationMode.TAXPAYER


def test_browser_sends_uploaded_session_with_consultation() -> None:
    js = Path("app/web/static/js/app.js").read_text(encoding="utf-8")

    assert "jurisprudence_session_id:" in js
    assert "jurisprudenceSession.sessionId" in js


def test_runtime_uses_hybrid_session_jurisprudence_wrapper() -> None:
    source = Path("app/web/runtime_runner.py").read_text(encoding="utf-8")

    assert "load_web_jurisprudence_session(" in source
    assert "run_hybrid_with_session_jurisprudence(" in source
    assert "session_jurisprudence_documents=session_documents" in source
    assert "explanation_mode=_explanation_mode(request.mode)" in source


def test_runtime_projects_session_jurisprudence_as_web_evidence() -> None:
    source = Path("app/web/runtime_runner.py").read_text(encoding="utf-8")

    assert '"role": "jurisprudence"' in source
    assert '"source_label": "Jurisprudencia temporal"' in source
    assert '"applicable_candidate": assessment.applicable_candidate' in source
