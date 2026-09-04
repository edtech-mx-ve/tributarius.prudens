from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class HybridContractKind(StrEnum):
    PYDANTIC_MODEL = "pydantic_model"
    ENUM = "enum"
    CALLABLE = "callable"


class HybridContractSpec(BaseModel):
    """Contrato público mínimo que F.2-F.12 deben conservar de forma aditiva."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str = Field(pattern=r"^F1-[A-Z0-9_-]{3,80}$")
    component: str = Field(min_length=2, max_length=100)
    kind: HybridContractKind
    import_path: str = Field(min_length=3, max_length=300)
    required_fields: list[str] = Field(default_factory=list, max_length=100)
    required_values: list[str] = Field(default_factory=list, max_length=100)
    required_parameters: list[str] = Field(default_factory=list, max_length=30)
    notes: str = Field(min_length=3, max_length=1000)

    @model_validator(mode="after")
    def validate_kind_payload(self) -> HybridContractSpec:
        populated = sum(
            bool(items)
            for items in (
                self.required_fields,
                self.required_values,
                self.required_parameters,
            )
        )
        if populated != 1:
            raise ValueError("Cada contrato F.1 debe declarar exactamente una forma verificable.")
        expected = {
            HybridContractKind.PYDANTIC_MODEL: bool(self.required_fields),
            HybridContractKind.ENUM: bool(self.required_values),
            HybridContractKind.CALLABLE: bool(self.required_parameters),
        }
        if not expected[self.kind]:
            raise ValueError("La forma declarada no corresponde al tipo de contrato F.1.")
        return self


class HybridRuntimeBaseline(BaseModel):
    """Estado productivo que F.1 congela sin activar todavía H1/H2 ni Llama real."""

    model_config = ConfigDict(extra="forbid")

    explanation_provider: str = "MockLLMProvider"
    explanation_runtime: str = "deterministic_mock_until_sprint20"
    legal_hypothesis_service_configured: bool = False
    real_llm_active: bool = False
    legacy_hypothesis_contract_preserved: bool = True
    jurisprudence_optional: bool = True
    additive_evolution_only: bool = True


class HybridContractBaseline(BaseModel):
    """Snapshot F.1 de compatibilidad para la evolución híbrida posterior."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    baseline_commit: str = Field(pattern=r"^[0-9a-f]{7,40}$")
    baseline_label: str = Field(min_length=3, max_length=120)
    runtime: HybridRuntimeBaseline
    contracts: list[HybridContractSpec] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_contract_ids(self) -> HybridContractBaseline:
        contract_ids = [item.contract_id for item in self.contracts]
        if len(contract_ids) != len(set(contract_ids)):
            raise ValueError("F.1 no admite contract_id duplicados.")
        return self


class HybridContractCheck(BaseModel):
    """Resultado individual de la auditoría de compatibilidad F.1."""

    model_config = ConfigDict(extra="forbid")

    contract_id: str
    component: str
    preserved: bool
    detail: str = Field(min_length=1, max_length=1000)


class HybridContractAudit(BaseModel):
    """Resultado canónico de F.1; no ejecuta ni modifica razonamiento jurídico."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    baseline_commit: str
    checks: list[HybridContractCheck] = Field(min_length=1, max_length=120)
    runtime_checks: list[HybridContractCheck] = Field(min_length=1, max_length=20)
    all_contracts_preserved: bool
    real_llm_activation_performed: bool = False
    h1_h2_runtime_activation_performed: bool = False
    runtime_order_changed: bool = False
    legal_decision_changed: bool = False
    additive_evolution_required: bool = True
