from __future__ import annotations

import hashlib

import pytest
from pydantic import ValidationError

from app.domain.legal_consultation_pdf_artifact import (
    LegalConsultationPdfArtifact,
)
from app.services.legal_consultation_pdf import (
    generate_legal_consultation_pdf,
)
from app.services.legal_consultation_pdf_artifact import (
    build_legal_consultation_pdf_artifact,
)
from tests.test_block_g1_legal_consultation_report import (
    _report,
)


def test_g11_sha256_matches_exact_pdf_bytes() -> None:
    report = _report()

    artifact = build_legal_consultation_pdf_artifact(
        report
    )

    expected = hashlib.sha256(
        artifact.pdf_bytes
    ).hexdigest()

    assert artifact.pdf_sha256 == expected
    assert len(artifact.pdf_sha256) == 64


def test_g11_preserves_canonical_source_identity() -> None:
    report = _report()

    artifact = build_legal_consultation_pdf_artifact(
        report
    )

    assert artifact.execution_id == report.execution_id
    assert artifact.folio == report.folio

    assert (
        artifact.source_canonical_result_sha256
        == report.canonical_result_sha256
    )


def test_g11_preserves_pdf_transport_metadata() -> None:
    report = _report()

    artifact = build_legal_consultation_pdf_artifact(
        report
    )

    assert artifact.media_type == "application/pdf"

    assert artifact.filename == (
        f"tributarius-prudens-{report.folio}.pdf"
    )

    assert artifact.content_length == len(
        artifact.pdf_bytes
    )

    assert artifact.pdf_bytes.startswith(b"%PDF-")


def test_g11_artifact_matches_g10_deterministic_pdf() -> None:
    report = _report()

    artifact = build_legal_consultation_pdf_artifact(
        report
    )

    direct_pdf = generate_legal_consultation_pdf(
        report
    )

    assert artifact.pdf_bytes == direct_pdf


def test_g11_same_report_produces_same_pdf_hash() -> None:
    report = _report()

    first = build_legal_consultation_pdf_artifact(
        report
    )
    second = build_legal_consultation_pdf_artifact(
        report
    )

    assert first.pdf_bytes == second.pdf_bytes
    assert first.pdf_sha256 == second.pdf_sha256


def test_g11_rejects_tampered_pdf_bytes() -> None:
    artifact = build_legal_consultation_pdf_artifact(
        _report()
    )

    payload = artifact.model_dump(mode="python")

    original = artifact.pdf_bytes
    tampered = (
        original[:-1]
        + bytes([original[-1] ^ 1])
    )

    assert len(tampered) == len(original)
    assert tampered != original
    assert tampered.startswith(b"%PDF-")

    payload["pdf_bytes"] = tampered

    with pytest.raises(
        ValidationError,
        match="huella PDF inconsistente",
    ):
        LegalConsultationPdfArtifact.model_validate(
            payload
        )


def test_g11_rejects_inconsistent_content_length() -> None:
    artifact = build_legal_consultation_pdf_artifact(
        _report()
    )

    payload = artifact.model_dump(mode="python")
    payload["content_length"] += 1

    with pytest.raises(
        ValidationError,
        match="longitud PDF inconsistente",
    ):
        LegalConsultationPdfArtifact.model_validate(
            payload
        )


def test_g11_does_not_change_legal_report() -> None:
    report = _report()

    before = report.model_dump(mode="json")

    build_legal_consultation_pdf_artifact(report)

    after = report.model_dump(mode="json")

    assert after == before
