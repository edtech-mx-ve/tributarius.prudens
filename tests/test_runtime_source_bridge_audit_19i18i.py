from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.runtime_source_bridge_audit import audit_runtime_source_bridge


def _write_policy(path: Path) -> None:
    path.write_text(
        json.dumps({"candidate_document_ids": ["doc_a"]}),
        encoding="utf-8",
    )


def _write_runtime(
    path: Path,
    *,
    filename: str,
    source_sha256: str,
) -> None:
    payload = {
        "text": "Artículo 1.",
        "metadata": {
            "document_id": "doc_a",
            "source_filename": filename,
            "source_sha256": source_sha256,
        },
    }
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")


def test_exact_local_pdf_hash_verifies_bridge(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "DOC_A.pdf"
    source.write_bytes(b"fake-pdf-source")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()

    policy = tmp_path / "policy.json"
    chunks = tmp_path / "chunks.jsonl"
    _write_policy(policy)
    _write_runtime(
        chunks,
        filename="DOC_A.pdf",
        source_sha256=source_sha,
    )

    summary = audit_runtime_source_bridge(
        chunks_path=chunks,
        content_policy_path=policy,
        corpus_dir=corpus,
    )

    assert summary.verified_documents == ("doc_a",)
    assert summary.blocked_documents == ()
    assert summary.public_release_allowed is False


def test_hash_mismatch_is_fail_closed(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "DOC_A.pdf").write_bytes(b"different")

    policy = tmp_path / "policy.json"
    chunks = tmp_path / "chunks.jsonl"
    _write_policy(policy)
    _write_runtime(
        chunks,
        filename="DOC_A.pdf",
        source_sha256="a" * 64,
    )

    summary = audit_runtime_source_bridge(
        chunks_path=chunks,
        content_policy_path=policy,
        corpus_dir=corpus,
    )

    assert summary.verified_documents == ()
    assert summary.hash_mismatch_documents == ("doc_a",)
    assert summary.blocked_documents == ("doc_a",)


def test_missing_source_file_is_fail_closed(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()

    policy = tmp_path / "policy.json"
    chunks = tmp_path / "chunks.jsonl"
    _write_policy(policy)
    _write_runtime(
        chunks,
        filename="DOC_A.pdf",
        source_sha256="a" * 64,
    )

    summary = audit_runtime_source_bridge(
        chunks_path=chunks,
        content_policy_path=policy,
        corpus_dir=corpus,
    )

    assert summary.verified_documents == ()
    assert summary.missing_source_files == ("doc_a",)
    assert summary.blocked_documents == ("doc_a",)


def test_hash_resolves_source_when_runtime_filename_is_alias(
    tmp_path: Path,
) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    source = corpus / "Nombre oficial distinto.pdf"
    source.write_bytes(b"same-pdf-source")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()

    policy = tmp_path / "policy.json"
    chunks = tmp_path / "chunks.jsonl"
    _write_policy(policy)
    _write_runtime(
        chunks,
        filename="canonical_doc_a.pdf",
        source_sha256=source_sha,
    )

    summary = audit_runtime_source_bridge(
        chunks_path=chunks,
        content_policy_path=policy,
        corpus_dir=corpus,
    )

    assert summary.verified_documents == ("doc_a",)
    assert summary.blocked_documents == ()
    assert summary.documents[0].filename_match is False
    assert summary.documents[0].sha256_match is True
    assert summary.documents[0].resolution_method == "sha256"
