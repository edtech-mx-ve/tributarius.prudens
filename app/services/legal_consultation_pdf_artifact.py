from __future__ import annotations

import hashlib

from app.domain.legal_consultation_pdf_artifact import (
    LegalConsultationPdfArtifact,
)
from app.domain.legal_consultation_report import (
    LegalConsultationReport,
)
from app.services.legal_consultation_pdf import (
    generate_legal_consultation_pdf,
)


def build_legal_consultation_pdf_artifact(
    report: LegalConsultationReport,
) -> LegalConsultationPdfArtifact:
    """Genera G.10 una vez y fija su integridad documental G.11."""

    pdf_bytes = generate_legal_consultation_pdf(report)

    pdf_sha256 = hashlib.sha256(
        pdf_bytes
    ).hexdigest()

    return LegalConsultationPdfArtifact(
        execution_id=report.execution_id,
        folio=report.folio,
        source_canonical_result_sha256=(
            report.canonical_result_sha256
        ),
        pdf_sha256=pdf_sha256,
        content_length=len(pdf_bytes),
        filename=(
            f"tributarius-prudens-{report.folio}.pdf"
        ),
        pdf_bytes=pdf_bytes,
    )
