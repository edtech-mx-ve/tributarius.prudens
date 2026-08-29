from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.services.runtime_browser_official_batch_import import (
    BatchImportError,
    import_batch,
)


def _pdf(path: Path, body: bytes = b"x") -> tuple[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.7\n" + body)
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def _base(tmp_path: Path) -> dict[str, Path]:
    downloads = tmp_path / "downloads"
    evidence = tmp_path / "evidence"
    downloads.mkdir()
    (evidence / "files").mkdir(parents=True)

    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "documents": [
                    {"document_id": "cpeum", "status": "pending_browser_download"},
                    {"document_id": "liva", "status": "pending_browser_download"},
                ]
            }
        ),
        encoding="utf-8",
    )
    registry = tmp_path / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "documents": {
                    "cpeum": {
                        "candidate_urls": [
                            "https://www.diputados.gob.mx/LeyesBiblio/pdf/CPEUM.pdf"
                        ]
                    },
                    "liva": {
                        "candidate_urls": [
                            "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIVA.pdf"
                        ]
                    },
                }
            }
        ),
        encoding="utf-8",
    )
    return {
        "downloads": downloads,
        "evidence": evidence,
        "plan": plan,
        "registry": registry,
        "manifest": evidence / "evidence_manifest.json",
        "report": tmp_path / "report.json",
    }


def test_stale_plan_skips_valid_existing_pending_document(tmp_path: Path) -> None:
    p = _base(tmp_path)
    sha, size = _pdf(p["evidence"] / "files" / "cpeum.pdf", b"official")
    p["manifest"].write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "document_id": "cpeum",
                        "source_url": (
                            "https://www.diputados.gob.mx/"
                            "LeyesBiblio/pdf/CPEUM.pdf"
                        ),
                        "sha256": sha,
                        "size_bytes": size,
                        "evidence_file": "files/cpeum.pdf",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _pdf(p["downloads"] / "liva.pdf", b"liva")

    report = import_batch(
        downloads_dir=p["downloads"],
        plan_path=p["plan"],
        registry_path=p["registry"],
        evidence_dir=p["evidence"],
        manifest_path=p["manifest"],
        report_path=p["report"],
    )

    assert report["imported_documents"] == ["liva"]
    assert report["skipped_existing_pending_documents"] == ["cpeum"]


def test_existing_pending_evidence_integrity_failure_blocks(tmp_path: Path) -> None:
    p = _base(tmp_path)
    sha, size = _pdf(p["evidence"] / "files" / "cpeum.pdf", b"original")
    p["manifest"].write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "document_id": "cpeum",
                        "source_url": (
                            "https://www.diputados.gob.mx/"
                            "LeyesBiblio/pdf/CPEUM.pdf"
                        ),
                        "sha256": sha,
                        "size_bytes": size,
                        "evidence_file": "files/cpeum.pdf",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    _pdf(p["evidence"] / "files" / "cpeum.pdf", b"tampered")
    _pdf(p["downloads"] / "liva.pdf", b"liva")

    with pytest.raises(BatchImportError, match="Integridad"):
        import_batch(
            downloads_dir=p["downloads"],
            plan_path=p["plan"],
            registry_path=p["registry"],
            evidence_dir=p["evidence"],
            manifest_path=p["manifest"],
            report_path=p["report"],
        )


def test_stale_plan_still_requires_missing_nonimported_pdf(tmp_path: Path) -> None:
    p = _base(tmp_path)
    sha, size = _pdf(p["evidence"] / "files" / "cpeum.pdf")
    p["manifest"].write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "document_id": "cpeum",
                        "source_url": (
                            "https://www.diputados.gob.mx/"
                            "LeyesBiblio/pdf/CPEUM.pdf"
                        ),
                        "sha256": sha,
                        "size_bytes": size,
                        "evidence_file": "files/cpeum.pdf",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(BatchImportError, match="liva.pdf"):
        import_batch(
            downloads_dir=p["downloads"],
            plan_path=p["plan"],
            registry_path=p["registry"],
            evidence_dir=p["evidence"],
            manifest_path=p["manifest"],
            report_path=p["report"],
        )
