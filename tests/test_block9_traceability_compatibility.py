from pathlib import Path


def test_traceability_preserves_query_fingerprint_api() -> None:
    source = Path("app/services/traceability.py").read_text(encoding="utf-8")

    assert "def verify_query_fingerprint(" in source
    assert "sha256_text(query) == trace.query_sha256" in source


def test_canonical_result_carries_new_traceable_channels() -> None:
    source = Path("app/domain/traceability.py").read_text(encoding="utf-8")

    assert "session_jurisprudence: dict[str, Any] | None = None" in source
    assert "llm_trace: dict[str, Any] | None = None" in source


def test_integrity_verifier_includes_new_traceable_channels() -> None:
    source = Path("app/services/traceability.py").read_text(encoding="utf-8")

    assert 'payload["session_jurisprudence"] = result.session_jurisprudence' in source
    assert 'payload["llm_trace"] = result.llm_trace' in source
