from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.hybrid_legal_verification import (
    H2SemanticVerificationDraft,
    HybridLegalSemanticVerificationDraft,
    HybridLegalVerificationPacket,
    HybridSemanticAssessment,
)
from app.domain.hybrid_llama_hypotheses import (
    FiscalHypothesisH1Draft,
    H1FactReference,
    JurisprudentialRatioH2Draft,
    JurisprudentialSupportSpan,
)
from app.domain.llama_hybrid_context import (
    InitialFiscalHypothesisContext,
    JurisprudentialRatioContext,
)


class CompactContractError(ValueError):
    """La salida compacta no puede expandirse al contrato canónico F.3/F.7."""


class CompactFiscalHypothesisH1Draft(BaseModel):
    """Transporte LLM mínimo H1; el sistema expande trazabilidad e invariantes."""

    model_config = ConfigDict(extra="forbid")

    legal_problem: str = Field(
        min_length=1,
        max_length=500,
        description=(
            "Problema fiscal inicial sin citas jurídicas específicas ni "
            "números de artículo."
        ),
    )
    proposition: str = Field(
        min_length=1,
        max_length=700,
        description=(
            "Hipótesis fiscal provisional sin citas jurídicas específicas, "
            "números de artículo, tesis, jurisprudencia, registros digitales "
            "ni identificadores normativos. Las referencias normativas se "
            "seleccionan exclusivamente mediante normative_ref_indices."
        ),
    )
    fact_indices: list[int] = Field(default_factory=list, max_length=6)
    institution_indices: list[int] = Field(default_factory=list, max_length=2)
    normative_ref_indices: list[int] = Field(
        default_factory=list,
        max_length=4,
        description=(
            "Índices del catálogo normativo autorizado. No copiar esas "
            "referencias dentro de proposition."
        ),
    )

    confidence_band: Literal["low", "medium", "high"] = "medium"

    @model_validator(mode="after")
    def validate_unique_indices(self) -> CompactFiscalHypothesisH1Draft:
        for values in (
            self.fact_indices,
            self.institution_indices,
            self.normative_ref_indices,
        ):
            if len(values) != len(set(values)):
                raise ValueError("La salida compacta H1 no admite índices duplicados.")
        return self


class CompactJurisprudentialRatioH2Draft(BaseModel):
    """Transporte LLM H2 mínimo: genera ratio y selecciona soporte por índice."""

    model_config = ConfigDict(extra="forbid")

    legal_question: str = Field(min_length=1, max_length=500)
    normative_ref_indices: list[int] = Field(default_factory=list, max_length=4)
    support_span_indices: list[int] = Field(min_length=1, max_length=4)
    proposed_ratio: str = Field(min_length=1, max_length=900)
    obiter_span_indices: list[int] = Field(default_factory=list, max_length=3)
    confidence_band: Literal["low", "medium", "high"] = "medium"

    @field_validator(
        "normative_ref_indices",
        "support_span_indices",
        "obiter_span_indices",
        mode="after",
    )
    @classmethod
    def canonicalize_duplicate_indices(cls, values: list[int]) -> list[int]:
        """Las listas de selección tienen semántica de conjunto, preservando orden."""

        return list(dict.fromkeys(values))

    @model_validator(mode="after")
    def validate_disjoint_support_and_obiter(self) -> CompactJurisprudentialRatioH2Draft:
        if set(self.support_span_indices) & set(self.obiter_span_indices):
            raise ValueError("H2 no puede clasificar el mismo span como ratio y obiter.")
        return self


class CompactH2SemanticAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_fidelity: HybridSemanticAssessment
    consistency_with_coordinated_argument: HybridSemanticAssessment


class CompactHybridLegalSemanticVerificationDraft(BaseModel):
    """Transporte LLM F.7 sin hashes, ids ni invariantes que el sistema ya conoce."""

    model_config = ConfigDict(extra="forbid")

    h1_consistency: HybridSemanticAssessment
    rbs_representation: HybridSemanticAssessment
    cbr_role: HybridSemanticAssessment
    h2_assessments: dict[str, CompactH2SemanticAssessment] = Field(
        default_factory=dict,
    )
    binding_jurisprudence_consistency: HybridSemanticAssessment
    contradiction_codes: list[str] = Field(default_factory=list, max_length=20)
    hallucination_signals: list[str] = Field(default_factory=list, max_length=20)
    requires_human_review: bool = False


def _indexed(values: list[str]) -> list[dict[str, Any]]:
    return [{"index": index, "value": value} for index, value in enumerate(values)]


def h1_compact_catalog(context: InitialFiscalHypothesisContext) -> dict[str, Any]:
    institutions = [
        value
        for value in (
            context.heuristic_route.primary_institution_id,
            context.heuristic_route.primary_institution_label,
        )
        if value
    ]
    institutions = list(dict.fromkeys(institutions))
    return {
        "facts": [
            {
                "index": index,
                "name": fact.name,
                "value": fact.value,
                "origin": fact.origin.value,
            }
            for index, fact in enumerate(context.facts)
        ],
        "institutions": _indexed(institutions),
        "normative_refs": _indexed(list(context.heuristic_route.exact_normative_hints)),
    }


def _confidence_from_band(value: Literal["low", "medium", "high"]) -> float:
    return {"low": 0.35, "medium": 0.60, "high": 0.80}[value]


def _restrict_array_indices(
    schema: dict[str, Any],
    *,
    property_name: str,
    allowed_indices: list[int],
) -> None:
    property_schema = schema["properties"][property_name]
    if not isinstance(property_schema, dict) or not allowed_indices:
        return
    property_schema["items"] = {
        "type": "integer",
        "enum": allowed_indices,
    }


def h1_compact_response_schema(
    context: InitialFiscalHypothesisContext,
) -> dict[str, Any]:
    """Esquema H1 ligado a los índices realmente disponibles en el contexto."""

    schema = CompactFiscalHypothesisH1Draft.model_json_schema()
    catalog = h1_compact_catalog(context)
    _restrict_array_indices(
        schema,
        property_name="fact_indices",
        allowed_indices=[item["index"] for item in catalog["facts"]],
    )
    _restrict_array_indices(
        schema,
        property_name="institution_indices",
        allowed_indices=[item["index"] for item in catalog["institutions"]],
    )
    _restrict_array_indices(
        schema,
        property_name="normative_ref_indices",
        allowed_indices=[item["index"] for item in catalog["normative_refs"]],
    )
    return schema


def expand_compact_h1(
    compact: CompactFiscalHypothesisH1Draft,
    *,
    context: InitialFiscalHypothesisContext,
) -> FiscalHypothesisH1Draft:
    catalog = h1_compact_catalog(context)
    facts = list(context.facts)
    institutions = [item["value"] for item in catalog["institutions"]]
    normative_refs = [item["value"] for item in catalog["normative_refs"]]

    try:
        facts_used = [
            H1FactReference(
                name=facts[index].name,
                value=facts[index].value,
                origin=facts[index].origin,
            )
            for index in compact.fact_indices
        ]
        selected_institutions = [str(institutions[index]) for index in compact.institution_indices]
        selected_norms = [str(normative_refs[index]) for index in compact.normative_ref_indices]
    except (IndexError, TypeError) as exc:
        raise CompactContractError(
            "H1 seleccionó un índice fuera del catálogo autorizado."
        ) from exc

    return FiscalHypothesisH1Draft(
        legal_problem=compact.legal_problem,
        proposition=compact.proposition,
        facts_used=facts_used,
        institutions=selected_institutions,
        candidate_normative_refs=selected_norms,
        candidate_normative_questions=[],
        assumptions=[],
        uncertainties=[],
        confidence=_confidence_from_band(compact.confidence_band),
    )


def _split_justification_candidates(text: str) -> list[str]:
    normalized = " ".join(text.split())
    if not normalized:
        return []
    pieces = [piece.strip() for piece in re.split(r"(?<=[.!?])\s+", normalized) if piece.strip()]
    if not pieces:
        pieces = [normalized]
    return list(dict.fromkeys(pieces))[:20]


def h2_compact_catalog(context: JurisprudentialRatioContext) -> dict[str, Any]:
    page = int(context.justification_source_pages[0])
    spans = _split_justification_candidates(context.justification_text)
    return {
        "normative_refs": _indexed(list(context.candidate_normative_refs)),
        "support_spans": [
            {"index": index, "page": page, "text": text}
            for index, text in enumerate(spans)
        ],
    }


def h2_compact_response_schema(
    context: JurisprudentialRatioContext,
) -> dict[str, Any]:
    """Esquema H2 con índices limitados al catálogo literal de Justificación."""

    schema = CompactJurisprudentialRatioH2Draft.model_json_schema()
    catalog = h2_compact_catalog(context)
    normative_indices = [item["index"] for item in catalog["normative_refs"]]
    span_indices = [item["index"] for item in catalog["support_spans"]]
    _restrict_array_indices(
        schema,
        property_name="normative_ref_indices",
        allowed_indices=normative_indices,
    )
    _restrict_array_indices(
        schema,
        property_name="support_span_indices",
        allowed_indices=span_indices,
    )
    _restrict_array_indices(
        schema,
        property_name="obiter_span_indices",
        allowed_indices=span_indices,
    )
    return schema


def expand_compact_h2(
    compact: CompactJurisprudentialRatioH2Draft,
    *,
    context: JurisprudentialRatioContext,
) -> JurisprudentialRatioH2Draft:
    catalog = h2_compact_catalog(context)
    norms = [item["value"] for item in catalog["normative_refs"]]
    spans = list(catalog["support_spans"])
    try:
        selected_norms = [str(norms[index]) for index in compact.normative_ref_indices]
        selected_spans = [
            JurisprudentialSupportSpan(
                text=str(spans[index]["text"]),
                page=int(spans[index]["page"]),
            )
            for index in compact.support_span_indices
        ]
        obiter_spans = [str(spans[index]["text"]) for index in compact.obiter_span_indices]
    except (IndexError, TypeError, KeyError) as exc:
        raise CompactContractError(
            "H2 seleccionó un índice fuera del catálogo autorizado."
        ) from exc

    return JurisprudentialRatioH2Draft(
        legal_question=compact.legal_question,
        material_facts=[],
        interpreted_norms=selected_norms,
        essential_premises=[span.text for span in selected_spans],
        proposed_ratio=compact.proposed_ratio,
        possible_obiter=obiter_spans,
        supporting_spans=selected_spans,
        uncertainties=[],
        confidence=_confidence_from_band(compact.confidence_band),
    )


def compact_verification_packet(packet: HybridLegalVerificationPacket) -> dict[str, Any]:
    coordination = packet.coordination
    h1 = (
        packet.h1_result.hypothesis
        if packet.h1_result is not None
        and packet.h1_result.generation_performed
        and packet.h1_result.hypothesis is not None
        else None
    )
    h2_rows: list[dict[str, object]] = []
    for index, item in enumerate(packet.h2_results):
        if not item.generation_performed or item.ratio is None:
            continue
        ratio = item.ratio
        h2_rows.append(
            {
                "ratio_index": index,
                "ratio_id": ratio.ratio_id,
                "document_id": ratio.document_id,
                "proposed_ratio": ratio.proposed_ratio,
                "essential_premises": list(ratio.essential_premises),
                "supporting_spans": [
                    {"text": span.text, "page": span.page}
                    for span in ratio.supporting_spans
                ],
                "interpreted_norms": list(ratio.interpreted_norms),
            }
        )

    application = packet.jurisprudence_application
    return {
        "canonical_conclusion": coordination.canonical_conclusion if coordination else None,
        "legal_authority_source": coordination.legal_authority_source if coordination else None,
        "applicable_normative_refs": (
            list(coordination.applicable_normative_refs) if coordination else []
        ),
        "h1": (
            {
                "hypothesis_id": h1.hypothesis_id,
                "proposition": h1.proposition,
                "candidate_normative_refs": list(h1.candidate_normative_refs),
            }
            if h1 is not None
            else None
        ),
        "rbs_h1": (
            {
                "relation": (
                    packet.rbs_h1_contrast.relation.value
                    if packet.rbs_h1_contrast is not None
                    and packet.rbs_h1_contrast.relation is not None
                    else None
                ),
                "rbs_conclusions": (
                    list(packet.rbs_h1_contrast.rbs_conclusions)
                    if packet.rbs_h1_contrast is not None
                    else []
                ),
                "authority_preserved": (
                    packet.rbs_h1_contrast.rbs_authority_preserved
                    if packet.rbs_h1_contrast is not None
                    else None
                ),
            }
        ),
        "cbr_h1": (
            {
                "effect": (
                    packet.cbr_h1_contrast.effect.value
                    if packet.cbr_h1_contrast is not None
                    and packet.cbr_h1_contrast.effect is not None
                    else None
                ),
                "selected_case_id": (
                    packet.cbr_h1_contrast.selected_case_id
                    if packet.cbr_h1_contrast is not None
                    else None
                ),
                "experiential_only": (
                    packet.cbr_h1_contrast.cbr_is_experiential_support
                    if packet.cbr_h1_contrast is not None
                    else None
                ),
            }
        ),
        "h2": h2_rows,
        "binding_jurisprudence": {
            "applicable_document_ids": (
                list(application.applicable_document_ids) if application is not None else []
            ),
            "decision_effect": (
                coordination.jurisprudence_effect.value if coordination is not None else "no_effect"
            ),
            "normative_basis_preserved": (
                coordination.normative_basis_preserved if coordination is not None else False
            ),
            "creates_second_conclusion": (
                coordination.jurisprudence_creates_second_conclusion
                if coordination is not None
                else False
            ),
        },
    }


def compact_verification_response_schema(
    packet: HybridLegalVerificationPacket,
) -> dict[str, Any]:
    """Restringe F.7 y fija una clave obligatoria por cada H2 generada."""

    schema = CompactHybridLegalSemanticVerificationDraft.model_json_schema()
    properties = schema["properties"]

    h1_present = bool(
        packet.h1_result is not None
        and packet.h1_result.generation_performed
        and packet.h1_result.hypothesis is not None
    )
    properties["h1_consistency"] = {
        "type": "string",
        "enum": (
            ["consistent", "inconsistent", "unresolved"]
            if h1_present
            else ["not_applicable"]
        ),
    }

    binding_present = bool(
        packet.jurisprudence_application is not None
        and packet.jurisprudence_application.applicable_document_ids
    )
    properties["binding_jurisprudence_consistency"] = {
        "type": "string",
        "enum": (
            ["consistent", "inconsistent", "unresolved"]
            if binding_present
            else ["not_applicable"]
        ),
    }

    generated_count = sum(
        1
        for item in packet.h2_results
        if item.generation_performed and item.ratio is not None
    )
    assessment_ref: dict[str, object] = {
        "$ref": "#/$defs/CompactH2SemanticAssessment",
    }
    keyed_assessments = {
        str(index): dict(assessment_ref)
        for index in range(generated_count)
    }
    h2_schema: dict[str, object] = {
        "type": "object",
        "properties": keyed_assessments,
        "additionalProperties": False,
    }
    if keyed_assessments:
        h2_schema["required"] = list(keyed_assessments)
    properties["h2_assessments"] = h2_schema

    return schema


def expand_compact_verification(
    compact: CompactHybridLegalSemanticVerificationDraft,
    *,
    packet: HybridLegalVerificationPacket,
    packet_sha256: str,
) -> HybridLegalSemanticVerificationDraft:
    generated = [
        item.ratio
        for item in packet.h2_results
        if item.generation_performed and item.ratio is not None
    ]
    expected_keys = {str(index) for index in range(len(generated))}
    observed_keys = set(compact.h2_assessments)
    if observed_keys != expected_keys:
        raise CompactContractError(
            "F.7 compacto no evaluó exactamente todas las H2 generadas."
        )

    assessments: list[H2SemanticVerificationDraft] = []
    for index, ratio in enumerate(generated):
        item = compact.h2_assessments[str(index)]
        assessments.append(
            H2SemanticVerificationDraft(
                ratio_id=ratio.ratio_id,
                source_fidelity=item.source_fidelity,
                consistency_with_coordinated_argument=(
                    item.consistency_with_coordinated_argument
                ),
            )
        )

    h1_present = bool(
        packet.h1_result is not None
        and packet.h1_result.generation_performed
        and packet.h1_result.hypothesis is not None
    )
    binding_present = bool(
        packet.jurisprudence_application is not None
        and packet.jurisprudence_application.applicable_document_ids
    )

    return HybridLegalSemanticVerificationDraft(
        packet_sha256=packet_sha256,
        h1_consistency=(
            compact.h1_consistency
            if h1_present
            else HybridSemanticAssessment.NOT_APPLICABLE
        ),
        rbs_representation=compact.rbs_representation,
        cbr_role=compact.cbr_role,
        h2_assessments=assessments,
        binding_jurisprudence_consistency=(
            compact.binding_jurisprudence_consistency
            if binding_present
            else HybridSemanticAssessment.NOT_APPLICABLE
        ),
        contradiction_codes=list(compact.contradiction_codes),
        hallucination_signals=list(compact.hallucination_signals),
        requires_human_review=compact.requires_human_review,
    )
