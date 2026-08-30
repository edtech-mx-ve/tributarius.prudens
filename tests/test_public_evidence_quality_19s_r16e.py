from app.services.public_evidence_quality_19s_r16e import (
    clean_public_evidence,
    reconcile_public_evidence_payload,
)


def test_clean_public_evidence_dedupes_ref_id_preserving_first() -> None:
    evidence = [
        {
            "ref_id": "a",
            "title": "Primera",
            "snippet": "texto 1",
        },
        {
            "ref_id": "a",
            "title": "Duplicada",
            "snippet": "texto 2",
        },
        {
            "ref_id": "b",
            "title": "Segunda",
            "snippet": "texto 3",
        },
    ]

    cleaned = clean_public_evidence(evidence)

    assert [item["ref_id"] for item in cleaned] == ["a", "b"]
    assert cleaned[0]["title"] == "Primera"


def test_clean_public_evidence_removes_structurally_empty_cards() -> None:
    evidence = [
        {},
        {
            "ref_id": "",
            "document_id": "",
            "title": " ",
            "unit": "",
            "snippet": "",
        },
        {
            "ref_id": "",
            "document_id": "liva",
            "title": "",
            "unit": "",
            "snippet": "",
        },
    ]

    cleaned = clean_public_evidence(evidence)

    assert cleaned == [
        {
            "ref_id": "",
            "document_id": "liva",
            "title": "",
            "unit": "",
            "snippet": "",
        }
    ]


def test_payload_reconciliation_is_non_mutating() -> None:
    payload = {
        "result": {
            "evidence": [
                {"ref_id": "x", "title": "Artículo 1"},
                {"ref_id": "x", "title": "Artículo 1 repetido"},
                {},
            ],
            "requires_human_review": True,
        }
    }

    reconciled = reconcile_public_evidence_payload(payload)

    assert len(reconciled["result"]["evidence"]) == 1
    assert len(payload["result"]["evidence"]) == 3
    assert reconciled["result"]["requires_human_review"] is True


def test_payload_without_evidence_is_preserved() -> None:
    payload = {"result": {"requires_human_review": False}}

    reconciled = reconcile_public_evidence_payload(payload)

    assert reconciled == payload
