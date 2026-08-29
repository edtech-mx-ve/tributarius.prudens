from __future__ import annotations

from typing import Any

import scripts.smoke_temporal_runtime_e2e_19i16 as smoke


def test_normative_refs_are_read_from_result_payload() -> None:
    payload: dict[str, Any] = {
        "evidence": [
            {"document_id": "liva"},
            {"document_id": "prodecon"},
        ],
        "applicable_normative_refs": [],
    }

    assert smoke._document_ids(payload) == {"liva", "prodecon"}
    assert smoke._normative_refs(payload) == []


def test_document_ids_ignore_non_dict_evidence_items() -> None:
    payload: dict[str, Any] = {
        "evidence": [
            {"document_id": "cpeum"},
            "invalid",
            None,
            {"document_id": ""},
        ],
        "applicable_normative_refs": [],
    }

    try:
        smoke._document_ids(payload)
    except smoke.SmokeFailure:
        pass
    else:
        raise AssertionError("La evidencia inválida debe fallar de forma explícita.")


def test_blocked_promotions_only_flags_refs_from_blocked_documents() -> None:
    payload: dict[str, Any] = {
        "evidence": [
            {"ref_id": "ref-liva", "document_id": "liva"},
            {"ref_id": "ref-rmf", "document_id": "rmf_2026"},
        ],
        "applicable_normative_refs": ["ref-rmf"],
    }

    assert smoke._blocked_promotions(
        payload,
        blocked_documents={"liva", "cpeum"},
    ) == []


def test_blocked_promotions_detects_blocked_document_ref() -> None:
    payload: dict[str, Any] = {
        "evidence": [
            {"ref_id": "ref-cpeum", "document_id": "cpeum"},
            {"ref_id": "ref-rmf", "document_id": "rmf_2026"},
        ],
        "applicable_normative_refs": ["ref-cpeum", "ref-rmf"],
    }

    assert smoke._blocked_promotions(
        payload,
        blocked_documents={"liva", "cpeum"},
    ) == [("ref-cpeum", "cpeum")]
