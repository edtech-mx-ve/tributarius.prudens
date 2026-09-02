from pathlib import Path

import pytest

from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.web.jurisprudence_upload import (
    WebJurisprudenceUploadError,
    process_web_jurisprudence_upload,
)


def test_web_exposes_real_pdf_input_and_upload_endpoint() -> None:
    html = Path("app/web/templates/index.html").read_text(encoding="utf-8")
    js = Path("app/web/static/js/app.js").read_text(encoding="utf-8")
    route = Path("app/api/routes/web.py").read_text(encoding="utf-8")

    assert 'id="jurisprudence-pdf"' in html
    assert 'accept="application/pdf,.pdf"' in html
    assert 'fetch("/api/v1/jurisprudence/session"' in js
    assert 'body: await file.arrayBuffer()' in js
    assert '"/api/v1/jurisprudence/session"' in route


def test_web_states_pdf_is_temporary_not_normative_corpus() -> None:
    html = Path("app/web/templates/index.html").read_text(encoding="utf-8")

    assert "evidencia jurisprudencial temporal" in html
    assert "no se incorpora" in html
    assert "corpus normativo" in html


def test_upload_rejects_non_pdf_before_pipeline(tmp_path: Path) -> None:
    with pytest.raises(WebJurisprudenceUploadError, match="Solo se aceptan archivos PDF"):
        process_web_jurisprudence_upload(
            content=b"contenido",
            filename="criterio.txt",
            temp_root=tmp_path,
        )


def test_upload_rejects_empty_file(tmp_path: Path) -> None:
    with pytest.raises(WebJurisprudenceUploadError, match="vacío"):
        process_web_jurisprudence_upload(
            content=b"",
            filename="criterio.pdf",
            temp_root=tmp_path,
        )


def test_upload_uses_isolated_session_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Path] = {}

    class FakeProcessed:
        pass

    representation = JurisprudenceDocumentRepresentation(
        document_id="jurisprudencia-test",
        original_filename="criterio.pdf",
        source_sha256="a" * 64,
        page_count=1,
        extracted_characters=18,
        pages=[
            JurisprudencePage(
                number=1,
                text="Criterio de prueba.",
                has_extractable_text=True,
            )
        ],
        full_text="Criterio de prueba.",
    )
    extracted = JurisprudenceExtractedMetadata(
        identifier="20260001",
        title="CRITERIO DE PRUEBA.",
        court_or_body="Primera Sala",
        source_pages=[1],
        requires_human_review=True,
    )

    def fake_ingest(path: Path, session_dir: Path) -> FakeProcessed:
        captured["path"] = path
        captured["session_dir"] = session_dir
        return FakeProcessed()

    monkeypatch.setattr(
        "app.web.jurisprudence_upload.ingest_jurisprudence_pdf",
        fake_ingest,
    )
    monkeypatch.setattr(
        "app.web.jurisprudence_upload.represent_jurisprudence_document",
        lambda processed: representation,
    )
    monkeypatch.setattr(
        "app.web.jurisprudence_upload.extract_jurisprudence_metadata",
        lambda document: extracted,
    )

    session_id, result_representation, result_metadata = (
        process_web_jurisprudence_upload(
            content=b"%PDF-1.4 test",
            filename="../criterio.pdf",
            temp_root=tmp_path,
        )
    )

    assert captured["session_dir"] == tmp_path.resolve() / session_id
    assert captured["path"].parent == captured["session_dir"] / "incoming"
    assert captured["path"].name == "criterio.pdf"
    assert result_representation is representation
    assert result_metadata is extracted
    assert (captured["session_dir"] / "session-jurisprudence.json").exists()
