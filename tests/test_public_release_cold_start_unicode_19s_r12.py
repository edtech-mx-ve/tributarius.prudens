from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np
import pytest

import app.services.public_release_cold_start_19i18n as n


def test_cold_start_module_contains_no_utf8_mojibake_markers() -> None:
    source = Path(n.__file__).read_text(encoding="utf-8")
    assert "Ã" not in source
    assert "Â" not in source


def test_release_contract_size_error_preserves_unicode(tmp_path: Path) -> None:
    extracted = tmp_path / "extracted"
    extracted.mkdir()
    n.write_json(
        extracted / "release_metadata.json",
        {
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
        },
    )
    payload = extracted / "runtime" / "chunks.jsonl"
    payload.parent.mkdir()
    payload.write_text("{}\n", encoding="utf-8")
    n.write_json(
        extracted / "release_manifest.json",
        {
            "candidate_only": True,
            "canonical_sha256": n.EXPECTED_CANONICAL_SHA256,
            "files": [
                {
                    "path": "runtime/chunks.jsonl",
                    "size": payload.stat().st_size + 1,
                    "sha256": n.sha256_file(payload),
                }
            ],
        },
    )
    with pytest.raises(n.ColdStartError, match="Tamaño divergente"):
        n.verify_release_contract(extracted)


def test_faiss_alignment_error_preserves_unicode(tmp_path: Path) -> None:
    index = faiss.IndexFlatIP(3)
    index.add(np.ones((2, 3), dtype="float32"))
    path = tmp_path / "index.faiss"
    faiss.write_index(index, str(path))
    with pytest.raises(n.ColdStartError, match="Desalineación FAISS/chunks"):
        n.probe_faiss(path, chunk_count=3)
