from pathlib import Path

import pytest

from app.domain.documents import ProcessedDocument, SourceType
from app.services import jurisprudence_ingestion
from app.services.document_pipeline import ExtractedPage, InvalidDocumentError
from app.services.jurisprudence_ingestion import (
    JurisprudenceIngestionPaths,
    ingest_jurisprudence_pdf,
)


def test_jurisprudence_paths_are_isolated_inside_session(tmp_path: Path) -> None:
    paths = JurisprudenceIngestionPaths.from_session_dir(tmp_path / "session-123")

    assert paths.root == (tmp_path / "session-123" / "jurisprudence").resolve()
    assert paths.normalized_dir == paths.root / "normalized"
    assert paths.metadata_dir == paths.root / "metadata"


def test_ingestion_forces_jurisprudence_source_type(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_process_pdf(
        input_path: Path,
        source_type: SourceType,
        output_dir: Path,
        metadata_dir: Path,
    ) -> ProcessedDocument:
        captured.update(
            input_path=input_path,
            source_type=source_type,
            output_dir=output_dir,
            metadata_dir=metadata_dir,
        )
        raise RuntimeError("sentinel")

    monkeypatch.setattr(jurisprudence_ingestion, "process_pdf", fake_process_pdf)

    pdf_path = tmp_path / "criterio.pdf"
    session_dir = tmp_path / "session"

    with pytest.raises(RuntimeError, match="sentinel"):
        ingest_jurisprudence_pdf(pdf_path, session_dir)

    assert captured["input_path"] == pdf_path
    assert captured["source_type"] is SourceType.JURISPRUDENCIA
    assert captured["output_dir"] == (
        session_dir / "jurisprudence" / "normalized"
    ).resolve()
    assert captured["metadata_dir"] == (
        session_dir / "jurisprudence" / "metadata"
    ).resolve()


def test_ingestion_reuses_real_document_pipeline(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf_path = tmp_path / "tesis.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\ntributarius-test")
    session_dir = tmp_path / "session"

    monkeypatch.setattr(
        "app.services.document_pipeline.extract_pdf_pages",
        lambda path: (
            [
                ExtractedPage(
                    number=1,
                    text="TESIS DE PRUEBA\nCriterio jurisprudencial extraíble.",
                )
            ],
            "test",
        ),
    )

    result = ingest_jurisprudence_pdf(pdf_path, session_dir)

    assert result.metadata.source_type is SourceType.JURISPRUDENCIA
    assert result.metadata.original_filename == "tesis.pdf"
    assert result.metadata.stats.page_count == 1
    assert result.metadata.stats.extracted_characters > 0
    assert "<!-- page:1 -->" in result.markdown

    normalized_path = Path(result.metadata.normalized_path)
    metadata_path = session_dir / "jurisprudence" / "metadata" / "tesis.json"

    assert normalized_path == (
        session_dir / "jurisprudence" / "normalized" / "tesis.md"
    ).resolve()
    assert normalized_path.exists()
    assert metadata_path.resolve().exists()


def test_ingestion_rejects_non_pdf_through_existing_validation(
    tmp_path: Path,
) -> None:
    text_path = tmp_path / "criterio.txt"
    text_path.write_text("no es PDF", encoding="utf-8")

    with pytest.raises(InvalidDocumentError, match="Solo se aceptan archivos PDF"):
        ingest_jurisprudence_pdf(text_path, tmp_path / "session")
