from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.runtime_publication_safety_audit import (
    RuntimePublicationSafetyError,
    audit_runtime_publication_safety,
)


def _write_chunks(path: Path) -> None:
    rows = [
        {"chunk_id": "a", "text": "uno", "metadata": {"document_id": "doc_a"}},
        {"chunk_id": "b", "text": "dos", "document_id": "doc_a"},
        {"chunk_id": "c", "text": "tres", "metadata": {"document_id": "doc_b"}},
    ]
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _write_policy(
    path: Path,
    *,
    doc_b_status: str = "unknown_requires_review",
) -> None:
    payload = {
        "schema_version": "1.0",
        "allowed_status": "public_redistribution_verified",
        "documents": [
            {
                "document_id": "doc_a",
                "redistribution_status": "public_redistribution_verified",
                "evidence": "https://example.invalid/license-a",
            },
            {
                "document_id": "doc_b",
                "redistribution_status": doc_b_status,
                "evidence": (
                    "https://example.invalid/license-b"
                    if doc_b_status == "public_redistribution_verified"
                    else None
                ),
            },
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_fail_closed_when_any_document_is_unverified(tmp_path: Path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    policy = tmp_path / "policy.json"
    _write_chunks(chunks)
    _write_policy(policy)

    summary = audit_runtime_publication_safety(
        chunks_path=chunks,
        policy_path=policy,
    )

    assert summary.runtime_chunks == 3
    assert summary.observed_documents == 2
    assert summary.verified_documents == 1
    assert summary.blocked_documents == 1
    assert summary.public_release_allowed is False


def test_allows_only_when_all_observed_documents_are_verified(
    tmp_path: Path,
) -> None:
    chunks = tmp_path / "chunks.jsonl"
    policy = tmp_path / "policy.json"
    _write_chunks(chunks)
    _write_policy(policy, doc_b_status="public_redistribution_verified")

    summary = audit_runtime_publication_safety(
        chunks_path=chunks,
        policy_path=policy,
    )

    assert summary.verified_documents == 2
    assert summary.blocked_documents == 0
    assert summary.public_release_allowed is True


def test_missing_policy_entry_blocks_release(tmp_path: Path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    policy = tmp_path / "policy.json"
    _write_chunks(chunks)
    _write_policy(policy)
    payload = json.loads(policy.read_text(encoding="utf-8"))
    payload["documents"] = payload["documents"][:1]
    policy.write_text(json.dumps(payload), encoding="utf-8")

    summary = audit_runtime_publication_safety(
        chunks_path=chunks,
        policy_path=policy,
    )

    assert summary.missing_policy_documents == 1
    assert summary.public_release_allowed is False


def test_verified_status_requires_explicit_evidence(tmp_path: Path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    policy = tmp_path / "policy.json"
    _write_chunks(chunks)
    payload = {
        "allowed_status": "public_redistribution_verified",
        "documents": [
            {
                "document_id": "doc_a",
                "redistribution_status": "public_redistribution_verified",
                "evidence": None,
            }
        ],
    }
    policy.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(
        RuntimePublicationSafetyError,
        match="requiere evidencia",
    ):
        audit_runtime_publication_safety(
            chunks_path=chunks,
            policy_path=policy,
        )
