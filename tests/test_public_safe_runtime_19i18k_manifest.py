from __future__ import annotations

import json
from pathlib import Path

from app.services.public_safe_runtime_19i18k import build_public_manifest


def test_manifest_rewrites_exact_promoted_chunks_field(tmp_path: Path) -> None:
    source = tmp_path / "manifest.json"
    source.write_text(
        json.dumps(
            {
                "promoted_chunks": 2981,
                "parent_count": 2981,
                "unrelated_number": 2981,
                "sha256": "old",
            }
        ),
        encoding="utf-8",
    )
    target = tmp_path / "public_manifest.json"
    old_canonical = tmp_path / "chunks_semantic_v2.jsonl"
    new_canonical = tmp_path / "chunks_normative.jsonl"

    build_public_manifest(
        source,
        target,
        old_canonical_path=old_canonical,
        new_canonical_path=new_canonical,
        old_parent_count=2981,
        new_parent_count=2962,
        old_sha256="old",
        new_sha256="new",
    )

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["promoted_chunks"] == 2962
    assert payload["parent_count"] == 2962
    assert payload["unrelated_number"] == 2981
    assert payload["sha256"] == "new"
    assert payload["public_runtime_parent_count"] == 2962
