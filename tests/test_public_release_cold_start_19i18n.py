from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import faiss
import numpy as np
import pytest

import app.services.public_release_cold_start_19i18n as n


def _json_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _build_fixture_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Path:
    staging = tmp_path / "staging"
    runtime = staging / "runtime"
    runtime.mkdir(parents=True)

    chunks: list[dict[str, object]] = []
    for idx, document_id in enumerate(sorted(n.ALLOWED_NORMATIVE_DOCUMENTS)):
        chunks.append(
            {
                "chunk_id": f"chunk-{idx}",
                "metadata": {"document_id": document_id},
                "text": f"Texto normativo {document_id}",
            }
        )
    chunks_path = runtime / "chunks.jsonl"
    chunks_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in chunks
        ),
        encoding="utf-8",
    )

    vectors = np.zeros((len(chunks), 4), dtype="float32")
    for idx in range(len(chunks)):
        vectors[idx, idx % 4] = 1.0 + idx / 100.0
    index = faiss.IndexFlatIP(4)
    index.add(vectors)
    faiss.write_index(index, str(runtime / "index.faiss"))

    (runtime / "manifest.json").write_text(
        json.dumps({"embedding_dimension": 4}) + "\n",
        encoding="utf-8",
    )

    metadata = {
        "candidate_only": True,
        "canonical_sha256": n.EXPECTED_CANONICAL_SHA256,
        "parent_count": n.EXPECTED_PARENT_COUNT,
        "normative_document_count": 14,
        "benchmark_passed": True,
        "blocked_content_absent": True,
        "provenance_complete": True,
        "temporal_fail_closed_complete": True,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "publication_legal_acceptance": False,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "automatic_publication_performed": False,
    }
    (staging / "release_metadata.json").write_bytes(_json_bytes(metadata))

    manifest_files = []
    for path in sorted(staging.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(staging).as_posix()
        manifest_files.append(
            {
                "path": rel,
                "size": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    manifest = {
        "candidate_only": True,
        "canonical_sha256": n.EXPECTED_CANONICAL_SHA256,
        "files": manifest_files,
    }
    (staging / "release_manifest.json").write_bytes(_json_bytes(manifest))

    candidate = tmp_path / "candidate.zip"
    with zipfile.ZipFile(candidate, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(staging.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(staging).as_posix())

    monkeypatch.setattr(
        n,
        "EXPECTED_CANDIDATE_SHA256",
        hashlib.sha256(candidate.read_bytes()).hexdigest(),
    )
    return candidate


def test_isolated_candidate_cold_start_passes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _build_fixture_candidate(tmp_path, monkeypatch)
    result = n.execute(
        candidate_zip=candidate,
        output_dir=tmp_path / "cold",
    )
    assert result["cold_start_acceptance"] is True
    assert result["chunk_count"] == 14
    assert result["faiss_ntotal"] == 14
    assert result["faiss_dimension"] == 4
    assert result["unique_document_count"] == 14
    assert result["runtime_loaded_from_extracted_candidate_only"] is True
    assert result["deployment_sufficiency_acceptance"] is False
    assert result["public_release_allowed"] is False


def test_zip_path_traversal_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = tmp_path / "bad.zip"
    with zipfile.ZipFile(candidate, "w") as archive:
        archive.writestr("../escape.txt", "x")
    monkeypatch.setattr(
        n,
        "EXPECTED_CANDIDATE_SHA256",
        hashlib.sha256(candidate.read_bytes()).hexdigest(),
    )
    with pytest.raises(n.ColdStartError, match="Path traversal"):
        n.validate_candidate_zip(candidate)


def test_manifest_hash_mismatch_is_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _build_fixture_candidate(tmp_path, monkeypatch)
    extracted = tmp_path / "extracted"
    n.extract_candidate(candidate, extracted)
    chunks = extracted / "runtime" / "chunks.jsonl"
    chunks.write_text(chunks.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")
    with pytest.raises(n.ColdStartError, match="Tamaño divergente|SHA divergente"):
        n.verify_release_contract(extracted)


def test_blocked_document_is_rejected(tmp_path: Path) -> None:
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text(
        json.dumps(
            {
                "chunk_id": "x",
                "metadata": {"document_id": "prodecon"},
                "text": "x",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(n.ColdStartError, match="Documento bloqueado"):
        n.load_chunks(chunks)


def test_faiss_chunk_count_mismatch_is_rejected(tmp_path: Path) -> None:
    index = faiss.IndexFlatIP(3)
    index.add(np.ones((2, 3), dtype="float32"))
    path = tmp_path / "index.faiss"
    faiss.write_index(index, str(path))
    with pytest.raises(n.ColdStartError, match="Desalineación FAISS/chunks"):
        n.probe_faiss(path, chunk_count=3)


def test_existing_output_is_not_overwritten(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    candidate = _build_fixture_candidate(tmp_path, monkeypatch)
    output = tmp_path / "cold"
    output.mkdir()
    with pytest.raises(n.ColdStartError, match="Output ya existe"):
        n.execute(candidate_zip=candidate, output_dir=output)
