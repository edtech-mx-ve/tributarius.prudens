from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.services.runtime_browser_evidence_bridge import (
    audit_browser_evidence_against_local_bridge,
)
from app.services.runtime_official_source_audit import OfficialSourceAuditError


def _write_registry(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "allowed_authority_hosts": ["www.diputados.gob.mx"],
                "documents": [
                    {
                        "document_id": "cff",
                        "candidate_urls": [
                            "https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf"
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_bridge(path: Path, sha256: str) -> None:
    path.write_text(
        json.dumps(
            {
                "documents": [
                    {
                        "document_id": "cff",
                        "local_source_sha256": sha256,
                        "resolved_source_path": "Corpus app/CFF.pdf",
                        "bridge_verified": True,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )


def _write_browser_evidence(base: Path, pdf_bytes: bytes) -> str:
    files = base / "files"
    files.mkdir(parents=True)
    pdf = files / "cff.pdf"
    pdf.write_bytes(pdf_bytes)
    digest = hashlib.sha256(pdf_bytes).hexdigest()
    (base / "evidence_manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "acquisition_mode": "browser_manual_official_url",
                "documents": [
                    {
                        "document_id": "cff",
                        "source_url": (
                            "https://www.diputados.gob.mx/"
                            "LeyesBiblio/pdf/CFF.pdf"
                        ),
                        "evidence_file": "files/cff.pdf",
                        "sha256": digest,
                        "size_bytes": len(pdf_bytes),
                        "acquisition_method": "manual_browser_official_url",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return digest


def test_exact_binary_match_verifies_official_binary_provenance(
    tmp_path: Path,
) -> None:
    evidence = tmp_path / "evidence"
    pdf_bytes = b"%PDF-1.7\nexact-official-binary"
    digest = _write_browser_evidence(evidence, pdf_bytes)
    registry = tmp_path / "registry.json"
    bridge = tmp_path / "bridge.json"
    _write_registry(registry)
    _write_bridge(bridge, digest)

    summary = audit_browser_evidence_against_local_bridge(
        browser_evidence_dir=evidence,
        bridge_report_path=bridge,
        candidate_registry_path=registry,
    )

    assert summary.exact_binary_verified_documents == ("cff",)
    assert summary.differing_binary_documents == ()
    assert summary.blocked_documents == ()
    assert summary.documents[0].official_binary_provenance_status == (
        "exact_binary_official_source_verified"
    )
    assert summary.public_release_allowed is False


def test_different_official_binary_is_fail_closed(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    _write_browser_evidence(evidence, b"%PDF-1.7\nofficial-new")
    registry = tmp_path / "registry.json"
    bridge = tmp_path / "bridge.json"
    _write_registry(registry)
    local_sha = hashlib.sha256(b"%PDF-1.7\nlocal-old").hexdigest()
    _write_bridge(bridge, local_sha)

    summary = audit_browser_evidence_against_local_bridge(
        browser_evidence_dir=evidence,
        bridge_report_path=bridge,
        candidate_registry_path=registry,
    )

    assert summary.exact_binary_verified_documents == ()
    assert summary.differing_binary_documents == ("cff",)
    assert summary.blocked_documents == ("cff",)
    assert summary.documents[0].official_binary_provenance_status == (
        "official_binary_differs_from_local_pdf"
    )


def test_tampered_browser_evidence_is_blocked(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    digest = _write_browser_evidence(evidence, b"%PDF-1.7\noriginal")
    (evidence / "files/cff.pdf").write_bytes(b"%PDF-1.7\ntampered")
    registry = tmp_path / "registry.json"
    bridge = tmp_path / "bridge.json"
    _write_registry(registry)
    _write_bridge(bridge, digest)

    summary = audit_browser_evidence_against_local_bridge(
        browser_evidence_dir=evidence,
        bridge_report_path=bridge,
        candidate_registry_path=registry,
    )

    assert summary.blocked_documents == ("cff",)
    assert summary.documents[0].evidence_integrity_ok is False
    assert summary.documents[0].official_binary_provenance_status == (
        "evidence_integrity_failed"
    )


def test_unregistered_source_url_is_rejected(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    digest = _write_browser_evidence(evidence, b"%PDF-1.7\noriginal")
    manifest_path = evidence / "evidence_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["documents"][0]["source_url"] = "https://example.com/CFF.pdf"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    registry = tmp_path / "registry.json"
    bridge = tmp_path / "bridge.json"
    _write_registry(registry)
    _write_bridge(bridge, digest)

    with pytest.raises(OfficialSourceAuditError):
        audit_browser_evidence_against_local_bridge(
            browser_evidence_dir=evidence,
            bridge_report_path=bridge,
            candidate_registry_path=registry,
        )
