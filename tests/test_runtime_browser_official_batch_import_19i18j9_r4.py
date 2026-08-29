from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.runtime_browser_official_batch_import import import_batch


def _pdf(path: Path, body: bytes) -> tuple[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.7\n" + body)
    data = path.read_bytes()
    return hashlib.sha256(data).hexdigest(), len(data)


def test_backward_compatible_preserved_existing_documents(tmp_path: Path) -> None:
    downloads = tmp_path / "downloads"
    evidence = tmp_path / "evidence"
    downloads.mkdir()
    (evidence / "files").mkdir(parents=True)

    sha, size = _pdf(evidence / "files" / "cff.pdf", b"cff")
    manifest = evidence / "evidence_manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "document_id": "cff",
                        "source_url": (
                            "https://www.diputados.gob.mx/"
                            "LeyesBiblio/pdf/CFF.pdf"
                        ),
                        "sha256": sha,
                        "size_bytes": size,
                        "evidence_file": "files/cff.pdf",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            {
                "documents": [
                    {"document_id": "liva", "status": "pending_browser_download"}
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
                    "liva": {
                        "candidate_urls": [
                            "https://www.diputados.gob.mx/LeyesBiblio/pdf/LIVA.pdf"
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    _pdf(downloads / "liva.pdf", b"liva")

    report = import_batch(
        downloads_dir=downloads,
        plan_path=plan,
        registry_path=registry,
        evidence_dir=evidence,
        manifest_path=manifest,
        report_path=tmp_path / "report.json",
    )

    assert report["preserved_existing_documents"] == ["cff"]
    assert report["existing_documents"] == ["cff"]
    assert report["skipped_existing_pending_documents"] == []
    assert report["imported_documents"] == ["liva"]
