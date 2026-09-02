from pathlib import Path

import pytest

from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.web.jurisprudence_session import (
    WebJurisprudenceSessionError,
    load_web_jurisprudence_session,
    save_web_jurisprudence_session,
)

SHA = "a" * 64
SESSION_ID = "b" * 32


def _representation() -> JurisprudenceDocumentRepresentation:
    text = "Criterio jurisprudencial de prueba."
    return JurisprudenceDocumentRepresentation(
        document_id="jurisprudencia-test",
        original_filename="criterio.pdf",
        source_sha256=SHA,
        page_count=1,
        extracted_characters=len(text),
        pages=[JurisprudencePage(number=1, text=text, has_extractable_text=True)],
        full_text=text,
    )


def _metadata() -> JurisprudenceExtractedMetadata:
    return JurisprudenceExtractedMetadata(
        identifier="20260001",
        title="CRITERIO DE PRUEBA.",
        court_or_body="Primera Sala",
        source_pages=[1],
        requires_human_review=True,
    )


def test_session_manifest_round_trip(tmp_path: Path) -> None:
    (tmp_path / SESSION_ID).mkdir()

    save_web_jurisprudence_session(
        session_id=SESSION_ID,
        representation=_representation(),
        metadata=_metadata(),
        temp_root=tmp_path,
    )
    representation, metadata = load_web_jurisprudence_session(
        SESSION_ID,
        temp_root=tmp_path,
    )

    assert representation.document_id == "jurisprudencia-test"
    assert metadata.identifier == "20260001"


def test_session_id_rejects_path_traversal(tmp_path: Path) -> None:
    with pytest.raises(WebJurisprudenceSessionError, match="inválido"):
        load_web_jurisprudence_session("../escape", temp_root=tmp_path)


def test_missing_session_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(WebJurisprudenceSessionError, match="no existe"):
        load_web_jurisprudence_session(SESSION_ID, temp_root=tmp_path)
