from __future__ import annotations

import pytest

from app.services.semantic_runtime_smoke import (
    SemanticRuntimeSmokeError,
    SmokeExpectation,
    assert_smoke_result,
    inspect_consultation_payload,
)


def test_inspect_consultation_payload_finds_expected_document() -> None:
    expectation = SmokeExpectation(
        case_id="liva",
        query="IVA",
        expected_document_id="liva",
    )
    payload = {
        "status": "ready",
        "result": {
            "evidence": [
                {
                    "kind": "document",
                    "metadata": {"document_id": "liva"},
                }
            ],
            "normative": {"applicable_refs": []},
            "jurisprudence": {"items": []},
        },
    }

    result = inspect_consultation_payload(payload, expectation)
    assert result.primary_document_found is True
    assert result.evidence_count == 1
    assert_smoke_result(result)


def test_inspect_consultation_payload_rejects_not_configured() -> None:
    expectation = SmokeExpectation(
        case_id="liva",
        query="IVA",
        expected_document_id="liva",
    )
    with pytest.raises(SemanticRuntimeSmokeError):
        inspect_consultation_payload(
            {"status": "not_configured", "result": None},
            expectation,
        )


def test_inspect_consultation_payload_reads_flat_presenter_document_id() -> None:
    expectation = SmokeExpectation(
        case_id="cpeum",
        query="Constitución",
        expected_document_id="cpeum",
    )
    payload = {
        "status": "ready",
        "result": {
            "evidence": [
                {
                    "kind": "document",
                    "document_id": "cpeum",
                    "source_reference": "cpeum.md",
                }
            ],
            "normative": {"applicable_refs": []},
            "jurisprudence": {"items": []},
        },
    }
    result = inspect_consultation_payload(payload, expectation)
    assert result.returned_document_ids == ("cpeum",)
    assert result.primary_document_found is True


def test_source_reference_md_is_normalized_as_fallback_document_id() -> None:
    expectation = SmokeExpectation(
        case_id="liva",
        query="IVA",
        expected_document_id="liva",
    )
    payload = {
        "status": "ready",
        "result": {
            "evidence": [
                {
                    "kind": "document",
                    "document_id": None,
                    "source_reference": "liva.md",
                }
            ],
            "normative": {"applicable_refs": []},
            "jurisprudence": {"items": []},
        },
    }
    result = inspect_consultation_payload(payload, expectation)
    assert result.returned_document_ids == ("liva",)
    assert result.primary_document_found is True


def test_normative_refs_are_read_from_presenter_contract() -> None:
    expectation = SmokeExpectation(
        case_id="liva",
        query="IVA",
        expected_document_id="liva",
    )
    payload = {
        "status": "ready",
        "result": {
            "evidence": [
                {
                    "kind": "document",
                    "document_id": "liva",
                    "source_reference": "liva.md",
                }
            ],
            "applicable_normative_refs": ["liva:article:1"],
        },
    }
    result = inspect_consultation_payload(payload, expectation)
    assert result.normative_reference_count == 1
