from __future__ import annotations

import json
from pathlib import Path

from app.services.runtime_official_source_audit import (
    OfficialSourceAuditError,
    RemoteArtifact,
    audit_official_source_provenance,
)


def _bridge(path: Path, *, sha: str = "a" * 64) -> None:
    payload = {
        "documents": [
            {
                "document_id": "doc_a",
                "resolved_source_path": "C:/corpus/DOC_A.pdf",
                "local_source_sha256": sha,
                "bridge_verified": True,
            }
        ]
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def _registry(path: Path, *, url: str = "https://dof.gob.mx/doc.pdf") -> None:
    payload = {
        "allowed_authority_hosts": ["dof.gob.mx"],
        "documents": [
            {
                "document_id": "doc_a",
                "candidate_urls": [url],
            }
        ],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_exact_remote_hash_verifies_official_provenance(tmp_path: Path) -> None:
    bridge = tmp_path / "bridge.json"
    registry = tmp_path / "registry.json"
    _bridge(bridge)
    _registry(registry)

    def fake_fetch(
        url: str,
        allowed_hosts: set[str],
        timeout_seconds: int,
        max_bytes: int,
    ) -> RemoteArtifact:
        assert allowed_hosts == {"dof.gob.mx"}
        assert timeout_seconds > 0
        assert max_bytes > 0
        return RemoteArtifact(
            requested_url=url,
            final_url=url,
            sha256="a" * 64,
            size_bytes=100,
        )

    summary = audit_official_source_provenance(
        bridge_report_path=bridge,
        candidate_registry_path=registry,
        fetcher=fake_fetch,
    )

    assert summary.official_provenance_verified_documents == ("doc_a",)
    assert summary.official_provenance_blocked_documents == ()
    assert summary.public_release_allowed is False
    assert summary.promotion_ready_documents == ()


def test_remote_hash_mismatch_is_fail_closed(tmp_path: Path) -> None:
    bridge = tmp_path / "bridge.json"
    registry = tmp_path / "registry.json"
    _bridge(bridge)
    _registry(registry)

    def fake_fetch(
        url: str,
        allowed_hosts: set[str],
        timeout_seconds: int,
        max_bytes: int,
    ) -> RemoteArtifact:
        return RemoteArtifact(
            requested_url=url,
            final_url=url,
            sha256="b" * 64,
            size_bytes=100,
        )

    summary = audit_official_source_provenance(
        bridge_report_path=bridge,
        candidate_registry_path=registry,
        fetcher=fake_fetch,
    )

    assert summary.official_provenance_verified_documents == ()
    assert summary.official_provenance_blocked_documents == ("doc_a",)


def test_non_https_candidate_is_rejected(tmp_path: Path) -> None:
    bridge = tmp_path / "bridge.json"
    registry = tmp_path / "registry.json"
    _bridge(bridge)
    _registry(registry, url="http://dof.gob.mx/doc.pdf")

    try:
        audit_official_source_provenance(
            bridge_report_path=bridge,
            candidate_registry_path=registry,
        )
    except OfficialSourceAuditError as exc:
        assert "no HTTPS" in str(exc)
    else:
        raise AssertionError("HTTP debía ser rechazado.")


def test_unverified_local_bridge_is_rejected(tmp_path: Path) -> None:
    bridge = tmp_path / "bridge.json"
    registry = tmp_path / "registry.json"
    payload = {
        "documents": [
            {
                "document_id": "doc_a",
                "resolved_source_path": "C:/corpus/DOC_A.pdf",
                "local_source_sha256": "a" * 64,
                "bridge_verified": False,
            }
        ]
    }
    bridge.write_text(json.dumps(payload), encoding="utf-8")
    _registry(registry)

    try:
        audit_official_source_provenance(
            bridge_report_path=bridge,
            candidate_registry_path=registry,
        )
    except OfficialSourceAuditError as exc:
        assert "Puente local no verificado" in str(exc)
    else:
        raise AssertionError("Bridge no verificado debía ser rechazado.")


def test_registry_uses_exact_versioned_regulation_urls() -> None:
    registry_path = Path(
        "app/resources/runtime_official_source_candidates_19i18j.json"
    )
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    mapping = {
        item["document_id"]: item["candidate_urls"]
        for item in payload["documents"]
    }

    assert mapping["reg_lisr_060516"] == [
        "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LISR_060516.pdf"
    ]
    assert mapping["reg_liva_250914"] == [
        "https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LIVA_250914.pdf"
    ]
