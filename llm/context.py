from __future__ import annotations

from app.domain.documents import SourceType
from app.services.legal_explanation_profile import (
    build_mature_legal_explanation_context,
)
from llm.models import (
    DeterministicEvidence,
    EvidenceItem,
    ExplanationMode,
    LLMGenerationContext,
)
from rag.retrieval.models import RetrievalResult


def _evidence_from_retrieval(result: RetrievalResult) -> list[EvidenceItem]:
    return [
        EvidenceItem(
            chunk_id=hit.chunk_id,
            score=hit.score,
            source_type=hit.metadata.source_type,
            source_filename=hit.metadata.source_filename,
            legal_identifier=hit.metadata.legal_identifier,
            page_start=hit.metadata.page_start,
            fiscal_year=hit.metadata.fiscal_year,
            version_label=hit.metadata.version_label,
            text=hit.text,
        )
        for hit in result.hits
    ]


def build_controlled_legal_context(
    retrieval: RetrievalResult,
    *,
    deterministic_evidence: DeterministicEvidence | None = None,
    explanation_mode: ExplanationMode = ExplanationMode.PROFESSIONAL,
    jurisprudence_retrieval: RetrievalResult | None = None,
) -> LLMGenerationContext:
    """Construye la frontera de evidencia autorizada para generación LLM.

    La jurisprudencia es opcional y solo puede incorporarse desde una
    recuperación explícitamente clasificada como jurisprudencial.
    """
    evidence = _evidence_from_retrieval(retrieval)

    jurisprudence_evidence: list[EvidenceItem] = []
    if jurisprudence_retrieval is not None:
        jurisprudence_evidence = _evidence_from_retrieval(jurisprudence_retrieval)
        invalid = [
            item.chunk_id
            for item in jurisprudence_evidence
            if item.source_type != SourceType.JURISPRUDENCIA
        ]
        if invalid:
            raise ValueError(
                "La entrada jurisprudencial opcional contiene evidencia "
                "que no está clasificada como jurisprudencia."
            )

    combined_evidence = evidence + jurisprudence_evidence
    if len(combined_evidence) > 20:
        raise ValueError(
            "El contexto jurídico controlado excede el máximo de 20 evidencias."
        )

    deterministic = (
        deterministic_evidence.model_copy(deep=True)
        if deterministic_evidence is not None
        else DeterministicEvidence()
    )

    deterministic.prodecon_orientation_refs = [
        item.chunk_id for item in evidence if item.source_type == SourceType.PRODECON
    ]
    deterministic.unam_foundation_refs = [
        item.chunk_id for item in evidence if item.source_type == SourceType.UNAM
    ]
    deterministic.normative_evidence_refs = [
        item.chunk_id for item in evidence if item.source_type == SourceType.NORMATIVA
    ]
    if jurisprudence_retrieval is not None:
        deterministic.jurisprudential_criteria = [
            item.chunk_id for item in jurisprudence_evidence
        ]

    mature_context = build_mature_legal_explanation_context(
        deterministic,
        explanation_mode,
    )

    return LLMGenerationContext(
        question=retrieval.query,
        evidence=combined_evidence,
        deterministic_evidence=deterministic,
        explanation_mode=explanation_mode,
        audience_label=mature_context.profile.audience_label,
        communication_goal=mature_context.profile.communication_goal,
        presentation_sections=list(mature_context.profile.section_order),
        presentation_instructions=list(mature_context.profile.style_instructions),
    )
