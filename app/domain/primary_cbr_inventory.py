from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CurrentCBRComponent(BaseModel):
    """Componente preexistente inventariado en C.1."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    path: str = Field(min_length=3, max_length=300)
    role: str = Field(min_length=3, max_length=80)
    responsibility: str = Field(min_length=10, max_length=500)


class CurrentCBRInventory(BaseModel):
    """Inventario auditable del CBR existente antes del CBR Primario 1.0."""

    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    schema_version: str = Field(pattern=r"^1\.\d+$")
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    purpose: str = Field(min_length=20, max_length=1200)
    components: list[CurrentCBRComponent] = Field(min_length=1, max_length=100)
    case_schema_fields: list[str] = Field(min_length=1, max_length=100)
    query_schema_fields: list[str] = Field(min_length=1, max_length=100)
    case_statuses: list[str] = Field(min_length=1, max_length=20)
    retrievable_statuses: list[str] = Field(min_length=1, max_length=20)
    non_retrievable_statuses: list[str] = Field(min_length=1, max_length=20)
    similarity_fields: list[str] = Field(min_length=1, max_length=20)
    field_weights: dict[str, float] = Field(min_length=1, max_length=20)
    exact_fields: list[str] = Field(default_factory=list, max_length=20)
    semantic_token_fields: list[str] = Field(default_factory=list, max_length=20)
    optional_exact_fields: list[str] = Field(default_factory=list, max_length=20)
    critical_fields: list[str] = Field(min_length=1, max_length=20)
    minimum_retrieval_similarity: float = Field(ge=0.0, le=1.0)
    minimum_reuse_similarity: float = Field(ge=0.0, le=1.0)
    query_top_k_default: int = Field(ge=1, le=20)
    query_top_k_minimum: int = Field(ge=1, le=20)
    query_top_k_maximum: int = Field(ge=1, le=20)
    cbr_loader_max_bytes: int = Field(ge=1)
    query_loader_max_bytes: int = Field(ge=1)
    storage_table: str = Field(min_length=1, max_length=100)
    fixture_cases_file: str = Field(min_length=1, max_length=300)
    fixture_query_file: str = Field(min_length=1, max_length=300)
    fixture_case_ids: list[str] = Field(default_factory=list, max_length=100)
    fixture_case_count: int = Field(ge=0)
    source_tree_operational_case_files: list[str] = Field(default_factory=list, max_length=100)
    source_tree_operational_case_count: int = Field(ge=0)
    runtime_database_case_count_known: bool = False
    requires_anonymized_cases: bool = True
    requires_validated_cases: bool = True
    anonymizer_identifier_types: list[str] = Field(default_factory=list, max_length=20)
    retention_candidate_status: str = Field(min_length=1, max_length=50)
    retention_proposed_case_status: str = Field(min_length=1, max_length=50)
    primary_knowledge_cbr_families: list[str] = Field(default_factory=list, max_length=100)
    primary_knowledge_cbr_family_count: int = Field(ge=0)
    primary_family_registry_present_at_baseline: bool = False
    hybrid_orchestrator_integrated: bool = True
    cbr_traceability_integrated: bool = True
    cbr_is_normative_authority: bool = False
    can_modify_existing_cbr: bool = False

    @field_validator(
        "case_schema_fields",
        "query_schema_fields",
        "case_statuses",
        "retrievable_statuses",
        "non_retrievable_statuses",
        "similarity_fields",
        "exact_fields",
        "semantic_token_fields",
        "optional_exact_fields",
        "critical_fields",
        "fixture_case_ids",
        "source_tree_operational_case_files",
        "anonymizer_identifier_types",
        "primary_knowledge_cbr_families",
    )
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("C.1 no admite valores duplicados en el inventario CBR.")
        return values

    @model_validator(mode="after")
    def validate_inventory(self) -> CurrentCBRInventory:
        component_paths = [item.path for item in self.components]
        if len(component_paths) != len(set(component_paths)):
            raise ValueError("C.1 contiene componentes duplicados.")
        if self.fixture_case_count != len(self.fixture_case_ids):
            raise ValueError("fixture_case_count no coincide con el inventario C.1.")
        if self.source_tree_operational_case_count != len(
            self.source_tree_operational_case_files
        ):
            raise ValueError(
                "source_tree_operational_case_count no coincide con C.1."
            )
        if self.primary_knowledge_cbr_family_count != len(
            self.primary_knowledge_cbr_families
        ):
            raise ValueError(
                "primary_knowledge_cbr_family_count no coincide con C.1."
            )
        if set(self.retrievable_statuses) & set(self.non_retrievable_statuses):
            raise ValueError("Los estados recuperables y bloqueados deben ser disjuntos.")
        if set(self.retrievable_statuses) | set(self.non_retrievable_statuses) != set(
            self.case_statuses
        ):
            raise ValueError("C.1 debe clasificar todos los estados CBR actuales.")
        if set(self.field_weights) != set(self.similarity_fields):
            raise ValueError("Los pesos CBR deben cubrir exactamente los campos de similitud.")
        if abs(sum(self.field_weights.values()) - 1.0) > 1e-9:
            raise ValueError("Los pesos nominales CBR actuales deben sumar 1.0.")
        if not set(self.critical_fields) <= set(self.similarity_fields):
            raise ValueError("Los campos críticos deben pertenecer a la similitud CBR.")
        if self.query_top_k_minimum > self.query_top_k_default:
            raise ValueError("El top_k por defecto no puede quedar bajo el mínimo.")
        if self.query_top_k_default > self.query_top_k_maximum:
            raise ValueError("El top_k por defecto no puede exceder el máximo.")
        if not self.requires_anonymized_cases or not self.requires_validated_cases:
            raise ValueError("C.1 debe preservar los controles de seguridad CBR existentes.")
        if self.runtime_database_case_count_known:
            raise ValueError(
                "C.1 no puede inferir desde el repositorio el número de casos en la BD runtime."
            )
        if not self.hybrid_orchestrator_integrated or not self.cbr_traceability_integrated:
            raise ValueError("C.1 debe registrar la integración CBR ya existente.")
        if self.cbr_is_normative_authority:
            raise ValueError("CBR no puede declararse autoridad normativa.")
        if self.can_modify_existing_cbr:
            raise ValueError("C.1 es inventario y no modifica el CBR preexistente.")
        return self
