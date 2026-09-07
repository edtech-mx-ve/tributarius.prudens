from __future__ import annotations

import hashlib
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LegalConsultationPdfArtifact(BaseModel):
    """G.11: PDF inmutable ligado a su resultado canonico y SHA-256."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: str = "1.0"

    execution_id: str = Field(
        pattern=r"^TP-[A-F0-9]{32}$"
    )
    folio: str = Field(
        pattern=r"^TP-\d{8}-[A-F0-9]{12}$"
    )

    source_canonical_result_sha256: str = Field(
        pattern=r"^[a-f0-9]{64}$"
    )

    pdf_sha256: str = Field(
        pattern=r"^[a-f0-9]{64}$"
    )

    content_length: int = Field(gt=0)

    media_type: Literal["application/pdf"] = (
        "application/pdf"
    )

    filename: str = Field(
        min_length=10,
        max_length=200,
    )

    pdf_bytes: bytes = Field(
        min_length=5,
        repr=False,
    )

    source_report_preserved: Literal[True] = True
    pdf_generated_once: Literal[True] = True
    sha256_computed_from_pdf_bytes: Literal[True] = True

    legal_reasoning_reexecuted: Literal[False] = False
    canonical_conclusion_recomputed: Literal[False] = False
    can_change_legal_result: Literal[False] = False

    @model_validator(mode="after")
    def validate_pdf_artifact(
        self,
    ) -> LegalConsultationPdfArtifact:
        if not self.pdf_bytes.startswith(b"%PDF-"):
            raise ValueError(
                "G.11 exige contenido PDF valido."
            )

        if self.content_length != len(self.pdf_bytes):
            raise ValueError(
                "G.11 detecto longitud PDF inconsistente."
            )

        expected_sha256 = hashlib.sha256(
            self.pdf_bytes
        ).hexdigest()

        if self.pdf_sha256 != expected_sha256:
            raise ValueError(
                "G.11 detecto una huella PDF inconsistente."
            )

        expected_filename = (
            f"tributarius-prudens-{self.folio}.pdf"
        )

        if self.filename != expected_filename:
            raise ValueError(
                "G.11 detecto nombre de archivo inconsistente."
            )

        return self
