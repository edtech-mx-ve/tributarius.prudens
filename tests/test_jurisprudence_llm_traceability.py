from pathlib import Path


def test_traceability_records_session_jurisprudence_sources() -> None:
    source = Path("app/services/traceability.py").read_text(encoding="utf-8")

    assert "session_jurisprudence_result" in source
    assert "session-jurisprudence:" in source
    assert 'kind=EvidenceKind.JURISPRUDENCE' in source


def test_jurisprudence_stage_merges_registered_and_session_evidence() -> None:
    source = Path("app/services/traceability.py").read_text(encoding="utf-8")

    assert "refs.extend(item.chunk_id" in source
    assert "_session_jurisprudence_event_refs(result)" in source


def test_session_jurisprudence_review_becomes_uncertainty() -> None:
    source = Path("app/services/traceability.py").read_text(encoding="utf-8")

    assert "SESSION_JURISPRUDENCE_REVIEW" in source
    assert "SESSION_JURISPRUDENCE_CONFLICT" in source


def test_canonical_payload_includes_session_jurisprudence_and_llm_trace() -> None:
    source = Path("app/services/traceability.py").read_text(encoding="utf-8")

    assert 'payload["session_jurisprudence"]' in source
    assert 'payload["llm_trace"]' in source


def test_llm_trace_remains_separate_from_jurisprudential_sources() -> None:
    source = Path("app/services/traceability.py").read_text(encoding="utf-8")

    assert "_llm_evidence(result)" in source
    assert "jurisprudential_sources=_jurisprudence_evidence(result)" in source
