from __future__ import annotations

from io import BytesIO

from pypdf import PdfReader

from app.services.legal_consultation_pdf import (
    generate_legal_consultation_pdf,
)
from tests.test_block_g1_legal_consultation_report import (
    _report,
)


def _pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))

    return "\n".join(
        page.extract_text() or ""
        for page in reader.pages
    )


def test_g10_generates_real_pdf_in_memory() -> None:
    report = _report()

    pdf_bytes = generate_legal_consultation_pdf(report)

    assert pdf_bytes.startswith(b"%PDF-")
    assert len(pdf_bytes) > 1000

    reader = PdfReader(BytesIO(pdf_bytes))

    assert len(reader.pages) >= 1


def test_g10_pdf_contains_canonical_report_identity() -> None:
    report = _report()

    text = _pdf_text(
        generate_legal_consultation_pdf(report)
    )

    normalized = " ".join(text.split())

    assert "TRIBUTARIUS PRUDENS" in normalized
    assert report.folio in normalized
    assert report.execution_id in normalized
    assert report.query_configuration.query in normalized
    assert report.canonical_result_sha256 in normalized


def test_g10_pdf_contains_all_required_sections() -> None:
    text = _pdf_text(
        generate_legal_consultation_pdf(_report())
    )

    normalized = " ".join(text.split())

    expected = [
        "1. Identificacion y configuracion",
        "2. Consulta",
        "3. Ruta heuristica",
        "4. RBS aplicado",
        "5. CBR recuperado",
        "6. Jurisprudencia de sesion",
        "7. Analisis juridico - Analyzer",
        "8. Determinacion juridica",
        "9. Explicacion segun modo",
        "10. Trazabilidad e integridad",
    ]

    for heading in expected:
        assert heading in normalized


def test_g10_prints_single_canonical_conclusion_block() -> None:
    report = _report()

    text = _pdf_text(
        generate_legal_consultation_pdf(report)
    )

    assert text.count("CONCLUSION CANONICA") == 1

    assert (
        report.legal_decision.conclusion
        == report.analyzer.canonical_conclusion
    )


def test_g10_preserves_source_report_without_mutation() -> None:
    report = _report()

    before = report.model_dump(mode="json")

    generate_legal_consultation_pdf(report)

    after = report.model_dump(mode="json")

    assert after == before


def test_g10_same_report_produces_identical_pdf_bytes() -> None:
    report = _report()

    first = generate_legal_consultation_pdf(report)
    second = generate_legal_consultation_pdf(report)

    assert first == second


def test_g10_uses_preserved_mode_explanation() -> None:
    report = _report()

    text = _pdf_text(
        generate_legal_consultation_pdf(report)
    )
    normalized = " ".join(text.split())

    projection = report.mode_explanation

    assert projection.mode.value in normalized
    assert projection.profile.audience_label in normalized

    explanation = projection.explanation
    assert explanation is not None

    summary = " ".join(
        explanation.answer.summary.split()
    )

    canonical = (
        report.legal_decision.conclusion or ""
    ).strip()

    if explanation.answer.summary.strip() != canonical:
        assert summary in normalized
