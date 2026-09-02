from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.security.input_guard import validate_text_safety


class WebConsultationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=3, max_length=4000)
    mode: str = Field(default="taxpayer", pattern=r"^(taxpayer|student|professional)$")
    fiscal_year: int | None = Field(default=None, ge=1900, le=2200)
    jurisprudence_session_id: str | None = Field(
        default=None,
        pattern=r"^[a-f0-9]{32}$",
    )

    @field_validator("query")
    @classmethod
    def clean_query(cls, value: str) -> str:
        clean = validate_text_safety(value)
        if len(clean) < 3:
            raise ValueError("La consulta debe contener al menos 3 caracteres.")
        return clean


class WebConsultationResponse(BaseModel):
    status: str = Field(pattern=r"^(ready|not_configured|error)$")
    message: str
    result: dict[str, object] | None = None


class WebJurisprudenceUploadResponse(BaseModel):
    status: str = Field(pattern=r"^(ready|error)$")
    message: str
    session_id: str | None = None
    document_id: str | None = None
    filename: str | None = None
    page_count: int | None = Field(default=None, ge=1)
    warnings: list[str] = Field(default_factory=list)
    extracted_metadata: dict[str, object] | None = None
