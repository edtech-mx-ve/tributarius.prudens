from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from app.services.selective_official_corpus_rebuild import (
    SelectiveOfficialRebuildError,
    TargetSource,
    _replace_by_local_identity,
    _targets,
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_targets_accepts_exact_authorized_pair() -> None:
    rows = []
    for doc in ("lfdc", "reg_liva_250914"):
        rows.append(
            {
                "document_id": doc,
                "local_pdf": f"local/{doc}.pdf",
                "official_pdf": f"official/{doc}.pdf",
                "local_sha256": "a" * 64,
                "official_sha256": "b" * 64,
            }
        )
    result = _targets(
        {
            "sprint": "19I.18J.12",
            "rebuild_authorized": True,
            "targets": rows,
        }
    )
    assert [item.document_id for item in result] == [
        "lfdc",
        "reg_liva_250914",
    ]


def test_targets_rejects_missing_target() -> None:
    with pytest.raises(SelectiveOfficialRebuildError):
        _targets(
            {
                "sprint": "19I.18J.12",
                "rebuild_authorized": True,
                "targets": [],
            }
        )


def test_staging_replacement_uses_sha_not_filename(tmp_path: Path) -> None:
    staging = tmp_path / "corpus"
    staging.mkdir()
    local = staging / "LFDC-original-name.pdf"
    local.write_bytes(b"%PDF-1.7\nold")
    official = tmp_path / "official.pdf"
    official.write_bytes(b"%PDF-1.7\nnew")

    target = TargetSource(
        document_id="lfdc",
        local_pdf=local,
        official_pdf=official,
        local_sha256=_sha(local),
        official_sha256=_sha(official),
    )
    name, sha = _replace_by_local_identity(staging, target)
    assert name == "LFDC-original-name.pdf"
    assert sha == _sha(official)
    assert _sha(local) == _sha(official)


def test_replacement_fails_closed_without_sha_match(tmp_path: Path) -> None:
    staging = tmp_path / "corpus"
    staging.mkdir()
    (staging / "LFDC.pdf").write_bytes(b"%PDF-1.7\nother")
    official = tmp_path / "official.pdf"
    official.write_bytes(b"%PDF-1.7\nnew")
    target = TargetSource(
        document_id="lfdc",
        local_pdf=tmp_path / "local.pdf",
        official_pdf=official,
        local_sha256="0" * 64,
        official_sha256=_sha(official),
    )
    with pytest.raises(SelectiveOfficialRebuildError):
        _replace_by_local_identity(staging, target)
