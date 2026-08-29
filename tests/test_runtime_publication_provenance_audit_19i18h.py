from __future__ import annotations

import json
from pathlib import Path

from app.services.runtime_publication_provenance_audit import (
    audit_runtime_publication_provenance,
)


def _write_policy(path: Path) -> None:
    payload = {
        "documents": [
            {
                "document_id": "doc_a",
                "allowed_authority_hosts": ["dof.gob.mx"],
                "requires_exact_source_provenance": True,
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_chunk(path: Path, *, source_url: str | None) -> None:
    metadata: dict[str, object] = {
        "document_id": "doc_a",
        "source_filename": "DOC_A.pdf",
        "source_sha256": "a" * 64,
    }
    if source_url is not None:
        metadata["source_url"] = source_url
    chunk = {"text": "Artículo 1.", "metadata": metadata}
    path.write_text(json.dumps(chunk) + "\n", encoding="utf-8")


def test_verified_https_authority_source_is_detected(tmp_path: Path) -> None:
    policy = tmp_path / "policy.json"
    chunks = tmp_path / "chunks.jsonl"
    _write_policy(policy)
    _write_chunk(chunks, source_url="https://dof.gob.mx/example")

    summary = audit_runtime_publication_provenance(
        chunks_path=chunks,
        policy_path=policy,
    )

    assert summary.provenance_verified_documents == ("doc_a",)
    assert summary.provenance_blocked_documents == ()
    assert summary.public_release_allowed is False
    assert summary.promotion_ready_documents == ()


def test_missing_source_url_is_fail_closed(tmp_path: Path) -> None:
    policy = tmp_path / "policy.json"
    chunks = tmp_path / "chunks.jsonl"
    _write_policy(policy)
    _write_chunk(chunks, source_url=None)

    summary = audit_runtime_publication_provenance(
        chunks_path=chunks,
        policy_path=policy,
    )

    assert summary.provenance_verified_documents == ()
    assert summary.provenance_blocked_documents == ("doc_a",)
    assert summary.documents[0].missing_source_url_chunks == 1


def test_disallowed_host_is_fail_closed(tmp_path: Path) -> None:
    policy = tmp_path / "policy.json"
    chunks = tmp_path / "chunks.jsonl"
    _write_policy(policy)
    _write_chunk(chunks, source_url="https://example.com/law.pdf")

    summary = audit_runtime_publication_provenance(
        chunks_path=chunks,
        policy_path=policy,
    )

    assert summary.provenance_verified_documents == ()
    assert summary.provenance_blocked_documents == ("doc_a",)
    assert summary.documents[0].disallowed_host_urls
