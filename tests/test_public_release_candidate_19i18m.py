from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

import app.services.public_release_candidate_19i18m as m


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    root = tmp_path / "public"
    canonical = root / "canonical" / "canonical.jsonl"
    canonical.parent.mkdir(parents=True)
    canonical.write_text('{"document_id":"cff","text":"x"}\n', encoding="utf-8")
    sha256 = hashlib.sha256(canonical.read_bytes()).hexdigest()
    monkeypatch.setattr(m, "PUBLIC_CANONICAL_SHA256", sha256)

    _write_json(
        root / "public_safe_runtime_acceptance.json",
        {
            "canonical_sha256": sha256,
            "parent_count": 2962,
            "benchmark_passed": True,
            "blocked_content_absent": True,
        },
    )
    runtime = root / "runtime"
    runtime.mkdir()
    _write_json(
        runtime / "metadata.json",
        {
            "document_id": "cff",
            "source_path": r"C:\Users\HP\Corpus app\CFF.pdf",
        },
    )
    (runtime / "index.faiss").write_bytes(b"FAISS")

    acceptance_l = tmp_path / "19l.json"
    _write_json(
        acceptance_l,
        {
            "public_runtime_sha256": sha256,
            "provenance_complete": True,
            "temporal_fail_closed_complete": True,
            "temporal_validity_complete": False,
            "redistribution_human_review_required": True,
            "legal_local_acceptance": True,
            "publication_legal_acceptance": False,
            "public_release_allowed": False,
            "git_push_allowed": False,
            "github_release_allowed": False,
            "render_deploy_allowed": False,
        },
    )
    return root, acceptance_l


def test_candidate_sanitizes_private_paths_and_stays_blocked(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, acceptance_l = _fixture(tmp_path, monkeypatch)
    output = tmp_path / "candidate"
    result = m.execute(
        runtime_root=root,
        acceptance_19l=acceptance_l,
        output_dir=output,
    )
    sanitized = json.loads(
        (output / "staging" / "runtime" / "metadata.json").read_text(
            encoding="utf-8"
        )
    )
    assert sanitized["source_path"] == "CFF.pdf"
    assert result["sanitized_private_path_values"] == 1
    assert result["absolute_private_path_scan_passed"] is True
    assert result["public_release_allowed"] is False


def test_legal_text_colon_sequences_are_not_windows_paths(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    _write_json(
        runtime / "chunks.jsonl",
        {
            "document_id": "cff",
            "text": (
                "Artículo 10.- Se considera domicilio fiscal: "
                "I. Tratándose de personas físicas: a) Cuando realizan "
                "actividades empresariales."
            ),
        },
    )
    m.audit_runtime_tree(runtime)


def test_real_windows_path_is_detected(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    _write_json(
        runtime / "chunks.jsonl",
        {
            "document_id": "cff",
            "text": r"build source: D:\Corpus app\CFF.pdf",
        },
    )
    with pytest.raises(m.ReleaseCandidateError):
        m.audit_runtime_tree(runtime)


def test_real_windows_path_is_sanitized(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    _write_json(
        runtime / "chunks.jsonl",
        {
            "document_id": "cff",
            "text": r"build source: D:\Corpus app\CFF.pdf",
        },
    )
    changed = m.sanitize_runtime_private_paths(runtime)
    assert changed == 1
    payload = json.loads(
        (runtime / "chunks.jsonl").read_text(encoding="utf-8")
    )
    assert payload["text"] == "build source: CFF.pdf"
    m.audit_runtime_tree(runtime)


def test_candidate_build_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, acceptance_l = _fixture(tmp_path, monkeypatch)
    result_a = m.execute(
        runtime_root=root,
        acceptance_19l=acceptance_l,
        output_dir=tmp_path / "a",
    )
    result_b = m.execute(
        runtime_root=root,
        acceptance_19l=acceptance_l,
        output_dir=tmp_path / "b",
    )
    assert result_a["zip_sha256"] == result_b["zip_sha256"]


def test_blocked_document_identity_is_rejected(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    _write_json(runtime / "metadata.json", {"document_id": "prodecon"})
    with pytest.raises(m.ReleaseCandidateError):
        m.audit_runtime_tree(runtime, allow_absolute_private_paths=True)


def test_forbidden_pdf_is_rejected(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "source.pdf").write_bytes(b"%PDF-")
    with pytest.raises(m.ReleaseCandidateError):
        m.audit_runtime_tree(runtime, allow_absolute_private_paths=True)


def test_zip_has_only_manifested_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root, acceptance_l = _fixture(tmp_path, monkeypatch)
    output = tmp_path / "candidate"
    m.execute(
        runtime_root=root,
        acceptance_19l=acceptance_l,
        output_dir=output,
    )
    zip_path = output / "tributarius-prudens-public-runtime-candidate.zip"
    with zipfile.ZipFile(zip_path) as archive:
        assert "release_manifest.json" in archive.namelist()
        assert "release_metadata.json" in archive.namelist()
        assert "runtime/index.faiss" in archive.namelist()
