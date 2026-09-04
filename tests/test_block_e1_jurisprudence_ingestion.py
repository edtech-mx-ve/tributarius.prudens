import json
from pathlib import Path

import pytest

from app.domain.jurisprudence_ingestion import JurisprudenceSourceScope
from app.services.document_pipeline import ExtractedPage, InvalidDocumentError
from app.services.jurisprudence_ingestion import (
    JurisprudenceIngestionPaths,
    ingest_jurisprudence_pdf_with_trace,
)
from app.web.jurisprudence_session import (
    load_web_jurisprudence_ingestion_receipt,
)
from app.web.jurisprudence_upload import (
    WebJurisprudenceUploadError,
    process_web_jurisprudence_upload,
)


def _patch_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.services.document_pipeline.extract_pdf_pages",
        lambda path: (
            [
                ExtractedPage(
                    number=1,
                    text=(
                        "Registro digital: 20260001\n"
                        "Rubro: APLICABILIDAD DE LA NORMA FISCAL.\n"
                        "La controversia exige determinar el alcance de la norma "
                        "para los hechos concretos del caso.\n"
                        "Artículo 5 del CFF."
                    ),
                ),
                ExtractedPage(
                    number=2,
                    text=(
                        "El criterio distingue un supuesto materialmente diferente y "
                        "explica cuándo la consecuencia jurídica resulta aplicable."
                    ),
                ),
            ],
            "test",
        ),
    )


def test_e1_ingestion_creates_session_scoped_chunks_and_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_extract(monkeypatch)
    pdf = tmp_path / "criterio.pdf"
    pdf.write_bytes(b"%PDF-1.7\ntributarius-e1")
    session_dir = tmp_path / "session-a"

    result = ingest_jurisprudence_pdf_with_trace(pdf, session_dir)
    paths = JurisprudenceIngestionPaths.from_session_dir(session_dir)

    assert result.receipt.jurisprudence_document_id == result.document.metadata.document_id
    assert result.receipt.source_sha256 == result.document.metadata.sha256
    assert result.receipt.source_scope is JurisprudenceSourceScope.SESSION
    assert result.receipt.user_attached is True
    assert result.receipt.persistent_corpus_member is False
    assert result.receipt.text_extracted is True
    assert result.receipt.page_count == 2
    assert result.receipt.chunk_count == len(result.chunks)
    assert result.receipt.chunk_count >= 2

    # E.1 sólo prueba integridad y extracción técnica, no autoridad jurídica.
    assert result.receipt.authenticity_verified is False
    assert result.receipt.temporal_validity_verified is False
    assert result.receipt.legal_applicability_evaluated is False
    assert result.receipt.can_control_legal_decision is False

    chunks_path = paths.chunks_dir / "criterio.jsonl"
    receipt_path = paths.ingestion_dir / "criterio.json"
    assert chunks_path.exists()
    assert receipt_path.exists()

    rows = [json.loads(line) for line in chunks_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == result.receipt.chunk_count
    assert all(row["metadata"]["source_type"] == "jurisprudencia" for row in rows)
    assert all(row["metadata"]["source_sha256"] == result.receipt.source_sha256 for row in rows)
    assert {row["metadata"]["page_start"] for row in rows} >= {1, 2}


def test_e1_same_document_keeps_stable_document_and_chunk_identity_across_sessions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_extract(monkeypatch)
    pdf = tmp_path / "criterio.pdf"
    pdf.write_bytes(b"%PDF-1.7\nidentical-source")

    first = ingest_jurisprudence_pdf_with_trace(pdf, tmp_path / "session-a")
    second = ingest_jurisprudence_pdf_with_trace(pdf, tmp_path / "session-b")

    assert first.receipt.source_sha256 == second.receipt.source_sha256
    assert first.receipt.jurisprudence_document_id == second.receipt.jurisprudence_document_id
    assert [item.chunk_id for item in first.chunks] == [item.chunk_id for item in second.chunks]


def test_e1_rejects_forged_pdf_extension_even_if_extraction_is_stubbed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_extract(monkeypatch)
    fake = tmp_path / "criterio.pdf"
    fake.write_bytes(b"plain text pretending to be a pdf")

    with pytest.raises(InvalidDocumentError, match="firma PDF válida"):
        ingest_jurisprudence_pdf_with_trace(fake, tmp_path / "session")


def test_web_failed_e1_ingestion_removes_temporary_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.web.jurisprudence_upload.uuid4",
        lambda: type("FixedUuid", (), {"hex": "a" * 32})(),
    )

    with pytest.raises(WebJurisprudenceUploadError):
        process_web_jurisprudence_upload(
            content=b"not-a-real-pdf",
            filename="criterio.pdf",
            temp_root=tmp_path,
        )

    assert not (tmp_path / ("a" * 32)).exists()


def test_web_session_persists_e1_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_extract(monkeypatch)

    session_id, _, _, receipt = process_web_jurisprudence_upload(
        content=b"%PDF-1.7\ntributarius-web-e1",
        filename="criterio.pdf",
        temp_root=tmp_path,
    )
    restored = load_web_jurisprudence_ingestion_receipt(
        session_id,
        temp_root=tmp_path,
    )

    assert restored is not None
    assert restored == receipt
    assert restored.source_scope is JurisprudenceSourceScope.SESSION
    assert restored.can_control_legal_decision is False
