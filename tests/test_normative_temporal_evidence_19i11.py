from __future__ import annotations

from app.services.normative_temporal_evidence_audit import (
    _TEMPORAL_SIGNAL_RE,
    _document_status,
)


def test_temporal_signal_detects_effective_language() -> None:
    assert _TEMPORAL_SIGNAL_RE.search(
        "El presente Decreto entrará en vigor el 1 de enero de 2026."
    )
    assert _TEMPORAL_SIGNAL_RE.search("ARTÍCULO PRIMERO TRANSITORIO")


def test_temporal_signal_does_not_treat_reform_date_as_effective_language() -> None:
    assert _TEMPORAL_SIGNAL_RE.search("Última reforma DOF 12-11-2021") is None


def test_document_status_is_fail_closed() -> None:
    assert (
        _document_status(
            normative_chunks=10,
            unknown=10,
            invalid=0,
        )
        == "temporal_metadata_unknown"
    )
    assert (
        _document_status(
            normative_chunks=10,
            unknown=0,
            invalid=1,
        )
        == "temporal_invalid_requires_review"
    )
