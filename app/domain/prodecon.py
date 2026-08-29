from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProdeconSectionSpec(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    section_id: str = Field(pattern=r"^PRODECON-\d{2}$")
    order: int = Field(ge=1, le=12)
    title: str = Field(min_length=3, max_length=200)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)
    module_key: str = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=100)
    module_name: str = Field(min_length=3, max_length=200)

    @model_validator(mode="after")
    def validate_pages(self) -> ProdeconSectionSpec:
        if self.page_end < self.page_start:
            raise ValueError("page_end no puede ser anterior a page_start")
        return self


class ProdeconSectionResult(BaseModel):
    section_id: str
    order: int
    title: str
    module_key: str
    module_name: str
    page_start: int
    page_end: int
    character_count: int = Field(ge=1)
    sha256: str = Field(min_length=64, max_length=64)
    output_path: str


class ProdeconIntegrationManifest(BaseModel):
    source_document_id: str
    source_sha256: str = Field(min_length=64, max_length=64)
    source_filename: str
    section_count: int = Field(ge=1)
    sections: list[ProdeconSectionResult]
    warnings: list[str] = Field(default_factory=list)
