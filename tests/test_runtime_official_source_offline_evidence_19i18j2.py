from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.runtime_official_source_offline_evidence import (
    audit_offline_official_evidence,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fixture(
    tmp_path: Path,
    *,
    local_bytes: bytes,
    evidence_bytes: bytes,
) -> tuple[Path, Path, Path]:
    local_sha = hashlib.sha256(local_bytes).hexdigest()
    evidence_sha = hashlib.sha256(evidence_bytes).hexdigest()

    bridge = tmp_path / "bridge.json"
    _write_json(
        bridge,
        {
            "documents": [
                {
                    "document_id": "cff",
                    "resolved_source_path": "C:/corpus/CFF.pdf",
                    "local_source_sha256": local_sha,
                    "bridge_verified": True,
                }
            ]
        },
    )

    registry = tmp_path / "registry.json"
    _write_json(
        registry,
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
        },
    )

    bundle = tmp_path / "bundle"
    files = bundle / "files"
    files.mkdir(parents=True)
    (files / "cff.pdf").write_bytes(evidence_bytes)
    _write_json(
        bundle / "evidence_manifest.json",
        {
            "records": [
                {
                    "document_id": "cff",
                    "source_url": (
                        "https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf"
                    ),
                    "final_url": (
                        "https://www.diputados.gob.mx/LeyesBiblio/pdf/CFF.pdf"
                    ),
                    "filename": "cff.pdf",
                    "sha256": evidence_sha,
                    "size_bytes": len(evidence_bytes),
                }
            ]
        },
    )
    return bridge, registry, bundle


def test_offline_exact_binary_match_verifies_provenance(tmp_path: Path) -> None:
    pdf = b"%PDF-1.7 exact"
    bridge, registry, bundle = _fixture(
        tmp_path,
        local_bytes=pdf,
        evidence_bytes=pdf,
    )

    summary = audit_offline_official_evidence(
        bridge_report_path=bridge,
        candidate_registry_path=registry,
        evidence_bundle_dir=bundle,
    )

    assert summary.verified_documents == ("cff",)
    assert summary.blocked_documents == ()
    assert summary.public_release_allowed is False
    assert summary.promotion_ready_documents == ()


def test_offline_different_official_binary_is_blocked(tmp_path: Path) -> None:
    bridge, registry, bundle = _fixture(
        tmp_path,
        local_bytes=b"%PDF-1.7 local",
        evidence_bytes=b"%PDF-1.7 current-official",
    )

    summary = audit_offline_official_evidence(
        bridge_report_path=bridge,
        candidate_registry_path=registry,
        evidence_bundle_dir=bundle,
    )

    assert summary.verified_documents == ()
    assert summary.blocked_documents == ("cff",)
    assert (
        summary.documents[0].blocked_reason
        == "official_binary_differs_from_local_pdf"
    )


def test_offline_tampered_evidence_is_blocked(tmp_path: Path) -> None:
    pdf = b"%PDF-1.7 exact"
    bridge, registry, bundle = _fixture(
        tmp_path,
        local_bytes=pdf,
        evidence_bytes=pdf,
    )
    (bundle / "files" / "cff.pdf").write_bytes(b"%PDF-1.7 tampered")

    summary = audit_offline_official_evidence(
        bridge_report_path=bridge,
        candidate_registry_path=registry,
        evidence_bundle_dir=bundle,
    )

    assert summary.verified_documents == ()
    assert summary.documents[0].blocked_reason == "evidence_integrity_failed"


def test_missing_offline_evidence_remains_fail_closed(tmp_path: Path) -> None:
    pdf = b"%PDF-1.7 exact"
    bridge, registry, bundle = _fixture(
        tmp_path,
        local_bytes=pdf,
        evidence_bytes=pdf,
    )
    _write_json(bundle / "evidence_manifest.json", {"records": []})
    (bundle / "files" / "cff.pdf").unlink()

    summary = audit_offline_official_evidence(
        bridge_report_path=bridge,
        candidate_registry_path=registry,
        evidence_bundle_dir=bundle,
    )

    assert summary.missing_evidence_documents == ("cff",)
    assert summary.blocked_documents == ("cff",)
