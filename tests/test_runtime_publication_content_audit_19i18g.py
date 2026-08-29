from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.runtime_publication_content_audit import (
    audit_runtime_publication_content,
)


def _write_policy(path: Path) -> None:
    payload = {
        "candidate_document_ids": ["doc_a"],
        "expected_source_type": "normativa",
        "expected_roles": {"doc_a": ["ley"]},
        "editorial_review_markers": ["nota del editor", "isbn"],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _chunk(text: str, *, role: str = "ley") -> dict[str, object]:
    return {
        "chunk_id": "chunk-0001",
        "text": text,
        "metadata": {
            "document_id": "doc_a",
            "source_type": "normativa",
            "source_role": role,
            "source_filename": "DOC_A.pdf",
            "source_sha256": "a" * 64,
            "retrieval_text_sha256": hashlib.sha256(
                text.encode("utf-8")
            ).hexdigest(),
        },
    }


def test_clean_candidate_passes_technical_conformity(tmp_path: Path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    policy = tmp_path / "policy.json"
    _write_policy(policy)
    chunks.write_text(
        json.dumps(_chunk("Artículo 1. Disposición normativa.")) + "\n",
        encoding="utf-8",
    )

    summary = audit_runtime_publication_content(
        chunks_path=chunks,
        content_policy_path=policy,
    )

    assert summary.candidate_documents == 1
    assert summary.technically_conformant_documents == ("doc_a",)
    assert summary.publication_promotion_allowed is False


def test_editorial_marker_requires_manual_review(tmp_path: Path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    policy = tmp_path / "policy.json"
    _write_policy(policy)
    chunks.write_text(
        json.dumps(_chunk("Nota del editor: texto adicional.")) + "\n",
        encoding="utf-8",
    )

    summary = audit_runtime_publication_content(
        chunks_path=chunks,
        content_policy_path=policy,
    )

    assert summary.manual_review_documents == ("doc_a",)
    assert summary.technically_conformant_documents == ()


def test_metadata_role_mismatch_fails_conformity(tmp_path: Path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    policy = tmp_path / "policy.json"
    _write_policy(policy)
    chunks.write_text(
        json.dumps(_chunk("Artículo 1.", role="doctrina")) + "\n",
        encoding="utf-8",
    )

    summary = audit_runtime_publication_content(
        chunks_path=chunks,
        content_policy_path=policy,
    )

    assert summary.metadata_nonconformant_documents == ("doc_a",)
    assert summary.technically_conformant_documents == ()
