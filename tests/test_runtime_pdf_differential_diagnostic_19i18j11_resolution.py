from __future__ import annotations

import hashlib
from pathlib import Path

from app.services.runtime_pdf_differential_diagnostic import _resolve_local_pdf


def _make_pdf(path: Path, body: bytes = b"x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.7\n" + body)
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_resolves_lfdc_by_alias_when_sha_field_is_absent(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    expected = _make_pdf(corpus / "LFDC.pdf")
    bridge = tmp_path / "reports" / "sprint19I18I" / "bridge.json"
    bridge.parent.mkdir(parents=True, exist_ok=True)
    bridge.write_text("{}", encoding="utf-8")

    resolved = _resolve_local_pdf(
        bridge,
        None,
        None,
        "lfdc",
        corpus,
    )
    assert resolved == expected


def test_resolves_reg_liva_by_browser_local_sha(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    expected = _make_pdf(corpus / "otra-copia.pdf", b"reg")
    bridge = tmp_path / "reports" / "sprint19I18I" / "bridge.json"
    bridge.parent.mkdir(parents=True, exist_ok=True)
    bridge.write_text("{}", encoding="utf-8")

    resolved = _resolve_local_pdf(
        bridge,
        None,
        {"local_sha256": _sha(expected)},
        "reg_liva_250914",
        corpus,
    )
    assert resolved == expected
