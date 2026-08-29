from __future__ import annotations

import json
from pathlib import Path

from app.services.selective_rebuild_delta import verify_selective_delta


def _manifest(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {"canonical_id": key, "source_sha256": value}
                    for key, value in values.items()
                ]
            }
        ),
        encoding="utf-8",
    )


def _md(root: Path, doc: str, text: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / f"{doc}.md").write_text(text, encoding="utf-8")


def test_accepts_only_authorized_delta(tmp_path: Path) -> None:
    current_manifest = tmp_path / "current.json"
    staged_manifest = tmp_path / "staged.json"
    current_root = tmp_path / "current"
    staged_root = tmp_path / "staged"
    docs = {
        "lfdc": "a" * 64,
        "reg_liva_250914": "b" * 64,
        "cff": "c" * 64,
    }
    staged = {
        "lfdc": "d" * 64,
        "reg_liva_250914": "e" * 64,
        "cff": "c" * 64,
    }
    _manifest(current_manifest, docs)
    _manifest(staged_manifest, staged)
    for doc in docs:
        _md(current_root, doc, f"old-{doc}")
        _md(staged_root, doc, f"new-{doc}" if doc != "cff" else f"old-{doc}")

    report = verify_selective_delta(
        current_manifest_path=current_manifest,
        staged_manifest_path=staged_manifest,
        current_normalized_root=current_root,
        staged_normalized_root=staged_root,
        output_path=tmp_path / "out.json",
    )
    assert report["delta_safe_for_candidate_build"] is True
    assert report["unauthorized_changed_documents"] == []


def test_rejects_unauthorized_normalized_delta(tmp_path: Path) -> None:
    current_manifest = tmp_path / "current.json"
    staged_manifest = tmp_path / "staged.json"
    current_root = tmp_path / "current"
    staged_root = tmp_path / "staged"
    docs = {
        "lfdc": "a" * 64,
        "reg_liva_250914": "b" * 64,
        "cff": "c" * 64,
    }
    staged = {
        "lfdc": "d" * 64,
        "reg_liva_250914": "e" * 64,
        "cff": "c" * 64,
    }
    _manifest(current_manifest, docs)
    _manifest(staged_manifest, staged)
    for doc in docs:
        _md(current_root, doc, f"old-{doc}")
        _md(staged_root, doc, f"new-{doc}")

    report = verify_selective_delta(
        current_manifest_path=current_manifest,
        staged_manifest_path=staged_manifest,
        current_normalized_root=current_root,
        staged_normalized_root=staged_root,
        output_path=tmp_path / "out.json",
    )
    assert report["delta_safe_for_candidate_build"] is False
    assert report["unauthorized_changed_documents"] == ["cff"]


def test_requires_both_authorized_source_replacements(tmp_path: Path) -> None:
    current_manifest = tmp_path / "current.json"
    staged_manifest = tmp_path / "staged.json"
    current_root = tmp_path / "current"
    staged_root = tmp_path / "staged"
    docs = {"lfdc": "a" * 64, "reg_liva_250914": "b" * 64}
    staged = {"lfdc": "d" * 64, "reg_liva_250914": "b" * 64}
    _manifest(current_manifest, docs)
    _manifest(staged_manifest, staged)
    for doc in docs:
        _md(current_root, doc, f"old-{doc}")
        _md(staged_root, doc, f"new-{doc}")

    report = verify_selective_delta(
        current_manifest_path=current_manifest,
        staged_manifest_path=staged_manifest,
        current_normalized_root=current_root,
        staged_normalized_root=staged_root,
        output_path=tmp_path / "out.json",
    )
    assert report["delta_safe_for_candidate_build"] is False
