from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.runtime_browser_official_batch_import import BatchImportError, import_batch


def _pdf(path: Path, body: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.7\n" + body)


def _setup(tmp_path: Path, ids: list[str]) -> dict[str, Path]:
    downloads = tmp_path / "downloads"
    evidence = tmp_path / "evidence"
    reports = tmp_path / "reports"
    downloads.mkdir()
    evidence.mkdir()
    (evidence / "files").mkdir()

    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"documents": [
        {"document_id": x, "status": "pending_browser_download"} for x in ids
    ]}), encoding="utf-8")
    registry = tmp_path / "registry.json"
    registry.write_text(json.dumps({"documents": {
        x: {"candidate_urls": [f"https://www.diputados.gob.mx/LeyesBiblio/pdf/{x}.pdf"]}
        for x in ids
    }}), encoding="utf-8")
    manifest = evidence / "evidence_manifest.json"
    manifest.write_text(json.dumps({"documents": [{
        "document_id": "cff", "source_url": "https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf",
        "sha256": "abc", "size_bytes": 10, "evidence_file": "files/cff.pdf",
        "acquisition_method": "manual_browser_official_url"
    }]}), encoding="utf-8")
    _pdf(evidence / "files" / "cff.pdf")
    return {
        "downloads": downloads, "evidence": evidence, "plan": plan,
        "registry": registry, "manifest": manifest, "report": reports / "report.json"
    }


def test_batch_success_preserves_existing(tmp_path: Path) -> None:
    p = _setup(tmp_path, ["liva", "lisr"])
    _pdf(p["downloads"] / "liva.pdf", b"liva")
    _pdf(p["downloads"] / "lisr.pdf", b"lisr")
    result = import_batch(
        downloads_dir=p["downloads"], plan_path=p["plan"], registry_path=p["registry"],
        evidence_dir=p["evidence"], manifest_path=p["manifest"], report_path=p["report"]
    )
    assert result["imported_count"] == 2
    assert result["preserved_existing_documents"] == ["cff"]
    assert (p["evidence"] / "files" / "cff.pdf").exists()
    assert (p["evidence"] / "files" / "liva.pdf").exists()


def test_missing_file_fails_before_mutation(tmp_path: Path) -> None:
    p = _setup(tmp_path, ["liva", "lisr"])
    _pdf(p["downloads"] / "liva.pdf")
    before = p["manifest"].read_bytes()
    with pytest.raises(BatchImportError, match="Falta PDF"):
        import_batch(
            downloads_dir=p["downloads"], plan_path=p["plan"], registry_path=p["registry"],
            evidence_dir=p["evidence"], manifest_path=p["manifest"], report_path=p["report"]
        )
    assert p["manifest"].read_bytes() == before
    assert not (p["evidence"] / "files" / "liva.pdf").exists()


def test_invalid_pdf_fails_closed(tmp_path: Path) -> None:
    p = _setup(tmp_path, ["liva"])
    (p["downloads"] / "liva.pdf").write_text("html", encoding="utf-8")
    with pytest.raises(BatchImportError, match="%PDF-"):
        import_batch(
            downloads_dir=p["downloads"], plan_path=p["plan"], registry_path=p["registry"],
            evidence_dir=p["evidence"], manifest_path=p["manifest"], report_path=p["report"]
        )


def test_untrusted_authority_rejected(tmp_path: Path) -> None:
    p = _setup(tmp_path, ["liva"])
    _pdf(p["downloads"] / "liva.pdf")
    p["registry"].write_text(json.dumps({"documents": {
        "liva": {"candidate_urls": ["https://example.com/LIVA.pdf"]}
    }}), encoding="utf-8")
    with pytest.raises(BatchImportError, match="Autoridad no permitida"):
        import_batch(
            downloads_dir=p["downloads"], plan_path=p["plan"], registry_path=p["registry"],
            evidence_dir=p["evidence"], manifest_path=p["manifest"], report_path=p["report"]
        )
