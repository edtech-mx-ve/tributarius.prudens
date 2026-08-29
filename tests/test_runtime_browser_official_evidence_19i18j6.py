from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.runtime_browser_official_evidence import (
    import_browser_downloaded_official_pdf,
)
from app.services.runtime_official_source_audit import OfficialSourceAuditError


def _registry(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "document_id": "cff",
                        "candidate_urls": [
                            "https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf"
                        ],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    return path


def test_imports_pdf_and_writes_hash_manifest(tmp_path: Path) -> None:
    pdf = tmp_path / "download.pdf"
    pdf.write_bytes(b"%PDF-1.7\nofficial-test")
    registry = _registry(tmp_path / "registry.json")
    output = tmp_path / "evidence"

    summary = import_browser_downloaded_official_pdf(
        document_id="cff",
        input_pdf=pdf,
        output_dir=output,
        registry_path=registry,
    )

    assert summary.imported_documents == ("cff",)
    copied = output / "files/cff.pdf"
    assert copied.read_bytes() == pdf.read_bytes()
    manifest = json.loads(
        (output / "evidence_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["documents"][0]["document_id"] == "cff"
    assert len(manifest["documents"][0]["sha256"]) == 64


def test_rejects_non_pdf(tmp_path: Path) -> None:
    bad = tmp_path / "fake.pdf"
    bad.write_bytes(b"<html>blocked</html>")
    registry = _registry(tmp_path / "registry.json")

    with pytest.raises(OfficialSourceAuditError, match="%PDF-"):
        import_browser_downloaded_official_pdf(
            document_id="cff",
            input_pdf=bad,
            output_dir=tmp_path / "evidence",
            registry_path=registry,
        )


def test_rejects_unknown_document(tmp_path: Path) -> None:
    pdf = tmp_path / "download.pdf"
    pdf.write_bytes(b"%PDF-1.7\nx")
    registry = _registry(tmp_path / "registry.json")

    with pytest.raises(OfficialSourceAuditError, match="no permitido"):
        import_browser_downloaded_official_pdf(
            document_id="unknown",
            input_pdf=pdf,
            output_dir=tmp_path / "evidence",
            registry_path=registry,
        )


def test_refuses_overwrite(tmp_path: Path) -> None:
    pdf = tmp_path / "download.pdf"
    pdf.write_bytes(b"%PDF-1.7\nx")
    registry = _registry(tmp_path / "registry.json")
    output = tmp_path / "evidence"

    import_browser_downloaded_official_pdf(
        document_id="cff",
        input_pdf=pdf,
        output_dir=output,
        registry_path=registry,
    )
    with pytest.raises(OfficialSourceAuditError, match="Ya existe"):
        import_browser_downloaded_official_pdf(
            document_id="cff",
            input_pdf=pdf,
            output_dir=output,
            registry_path=registry,
        )
