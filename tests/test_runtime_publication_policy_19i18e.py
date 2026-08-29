from __future__ import annotations

import json
from pathlib import Path

_EXPECTED_RUNTIME_DOCUMENT_IDS = {
    "cff",
    "cpeum",
    "lfdc",
    "lfisan",
    "lfpca",
    "lieps",
    "lif_2026",
    "lisr",
    "liva",
    "lotfja",
    "manual_derecho_fiscal_unam",
    "prodecon_contribuyente",
    "reg_cff",
    "reg_lisr_060516",
    "reg_liva_250914",
    "rmf_2026",
}


def test_publication_policy_matches_semantic_v2_document_ids() -> None:
    payload = json.loads(
        Path("app/resources/runtime_publication_policy_19i18e.json").read_text(
            encoding="utf-8"
        )
    )
    document_ids = {
        item["document_id"]
        for item in payload["documents"]
    }

    assert document_ids == _EXPECTED_RUNTIME_DOCUMENT_IDS
    assert len(document_ids) == 16


def test_initial_policy_remains_fail_closed() -> None:
    payload = json.loads(
        Path("app/resources/runtime_publication_policy_19i18e.json").read_text(
            encoding="utf-8"
        )
    )

    assert all(
        item["redistribution_status"] == "unknown_requires_review"
        for item in payload["documents"]
    )
    assert all(item["evidence"] is None for item in payload["documents"])
