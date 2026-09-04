from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from llm.models import LlamaStructuredAnswer, LLMGenerationContext


class CompactRAGContractError(ValueError):
    """La explicación compacta no puede expandirse al contrato canónico."""


class CompactRAGExplanationDraft(BaseModel):
    """Transporte breve para Llama real; referencias por índices autorizados."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=700)
    analysis: str = Field(min_length=1, max_length=1800)
    evidence_indices: list[int] = Field(default_factory=list, max_length=8)
    normative_ref_indices: list[int] = Field(default_factory=list, max_length=12)
    rule_ref_indices: list[int] = Field(default_factory=list, max_length=12)
    calculation_ref_indices: list[int] = Field(default_factory=list, max_length=8)
    cbr_ref_indices: list[int] = Field(default_factory=list, max_length=8)
    jurisprudence_ref_indices: list[int] = Field(default_factory=list, max_length=8)
    uncertainty_note: str | None = Field(default=None, max_length=500)
    requires_human_review: bool = False


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def rag_compact_catalog(context: LLMGenerationContext) -> dict[str, list[str]]:
    deterministic = context.deterministic_evidence
    return {
        "evidence_ids": [item.chunk_id for item in context.evidence],
        "normative_refs": (
            _unique(
                [
                    *deterministic.applicable_normative_refs,
                    *deterministic.normative_evidence_refs,
                ]
            )
            if deterministic is not None
            else []
        ),
        "rule_refs": (
            list(deterministic.rule_conclusions) if deterministic is not None else []
        ),
        "calculation_refs": (
            list(deterministic.calculations) if deterministic is not None else []
        ),
        "cbr_refs": (
            list(deterministic.similar_cases) if deterministic is not None else []
        ),
        "jurisprudence_refs": (
            list(deterministic.jurisprudential_criteria)
            if deterministic is not None
            else []
        ),
    }


def _restrict_array_indices(
    schema: dict[str, Any],
    *,
    property_name: str,
    count: int,
) -> None:
    property_schema = schema["properties"][property_name]
    if not isinstance(property_schema, dict):
        return
    if count == 0:
        properties = schema["properties"]
        if isinstance(properties, dict):
            properties.pop(property_name, None)
        return
    property_schema["items"] = {
        "type": "integer",
        "enum": list(range(count)),
    }


def rag_compact_response_schema(context: LLMGenerationContext) -> dict[str, Any]:
    """Liga cada índice a un catálogo ya autorizado por el sistema."""

    schema = CompactRAGExplanationDraft.model_json_schema()
    catalog = rag_compact_catalog(context)
    mapping = {
        "evidence_indices": "evidence_ids",
        "normative_ref_indices": "normative_refs",
        "rule_ref_indices": "rule_refs",
        "calculation_ref_indices": "calculation_refs",
        "cbr_ref_indices": "cbr_refs",
        "jurisprudence_ref_indices": "jurisprudence_refs",
    }
    for property_name, catalog_name in mapping.items():
        _restrict_array_indices(
            schema,
            property_name=property_name,
            count=len(catalog[catalog_name]),
        )
    return schema


def _select(values: list[str], indices: list[int], *, channel: str) -> list[str]:
    unique_indices = list(dict.fromkeys(indices))
    try:
        return [values[index] for index in unique_indices]
    except IndexError as exc:
        raise CompactRAGContractError(
            f"La explicación compacta seleccionó un índice inválido en {channel}."
        ) from exc


def expand_compact_rag_answer(
    compact: CompactRAGExplanationDraft,
    *,
    context: LLMGenerationContext,
) -> LlamaStructuredAnswer:
    catalog = rag_compact_catalog(context)
    deterministic = context.deterministic_evidence
    requires_review = compact.requires_human_review or bool(
        deterministic is not None and deterministic.requires_human_review
    )
    uncertainties = (
        [compact.uncertainty_note.strip()]
        if compact.uncertainty_note is not None and compact.uncertainty_note.strip()
        else []
    )

    return LlamaStructuredAnswer(
        summary=compact.summary,
        analysis=compact.analysis,
        evidence_ids=_select(
            catalog["evidence_ids"],
            compact.evidence_indices,
            channel="evidence_ids",
        ),
        normative_refs=_select(
            catalog["normative_refs"],
            compact.normative_ref_indices,
            channel="normative_refs",
        ),
        rule_refs=_select(
            catalog["rule_refs"],
            compact.rule_ref_indices,
            channel="rule_refs",
        ),
        calculation_refs=_select(
            catalog["calculation_refs"],
            compact.calculation_ref_indices,
            channel="calculation_refs",
        ),
        cbr_refs=_select(
            catalog["cbr_refs"],
            compact.cbr_ref_indices,
            channel="cbr_refs",
        ),
        jurisprudence_refs=_select(
            catalog["jurisprudence_refs"],
            compact.jurisprudence_ref_indices,
            channel="jurisprudence_refs",
        ),
        uncertainties=uncertainties,
        requires_human_review=requires_review,
        changes_deterministic_result=False,
        asserts_external_legal_authority=False,
    )
