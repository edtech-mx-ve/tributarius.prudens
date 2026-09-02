from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.domain.documents import ProcessedDocument, SourceType
from app.services.document_pipeline import process_pdf


@dataclass(frozen=True)
class JurisprudenceIngestionPaths:
    """Rutas aisladas para evidencia jurisprudencial aportada en una sesión."""

    root: Path
    normalized_dir: Path
    metadata_dir: Path

    @classmethod
    def from_session_dir(cls, session_dir: Path) -> JurisprudenceIngestionPaths:
        root = session_dir.expanduser().resolve() / "jurisprudence"
        return cls(
            root=root,
            normalized_dir=root / "normalized",
            metadata_dir=root / "metadata",
        )


def ingest_jurisprudence_pdf(
    input_path: Path,
    session_dir: Path,
) -> ProcessedDocument:
    """Ingiere un PDF jurisprudencial mediante el pipeline documental existente.

    La fuente queda tipificada siempre como jurisprudencia y sus salidas se
    escriben dentro del espacio de la sesión. Esta función no registra el
    documento en el corpus normativo ni determina su aplicabilidad jurídica.
    """
    paths = JurisprudenceIngestionPaths.from_session_dir(session_dir)
    return process_pdf(
        input_path=input_path,
        source_type=SourceType.JURISPRUDENCIA,
        output_dir=paths.normalized_dir,
        metadata_dir=paths.metadata_dir,
    )
