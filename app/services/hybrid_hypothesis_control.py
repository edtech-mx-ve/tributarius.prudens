from __future__ import annotations

import hashlib
import json
import re

from app.domain.hybrid_llama_hypotheses import (
    ControlledFiscalHypothesisH1,
    ControlledJurisprudentialRatioH2,
    FiscalHypothesisH1Draft,
    FiscalHypothesisH1Result,
    JurisprudentialRatioH2Draft,
    JurisprudentialRatioH2Result,
)
from app.domain.llama_hybrid_context import (
    InitialFiscalHypothesisContext,
    JurisprudentialRatioContext,
)


class HybridHypothesisValidationError(ValueError):
    """H1/H2 intentó cruzar la frontera de hechos, fuentes o autoridad permitida."""


def _canonical_digest(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_span(text: str) -> str:
    return " ".join(text.split()).casefold()


def _contains_explicit_authority_citation(text: str) -> bool:
    folded = text.casefold()
    patterns = (
        r"\bart[ií]culo\s+\d",
        r"\btesis\b",
        r"\bjurisprudencia\b",
        r"\bregistro\s+digital\b",
        r"\bp\.?\s*/\s*j\.\b",
    )
    return any(re.search(pattern, folded) for pattern in patterns)


def validate_fiscal_hypothesis_h1(
    draft: FiscalHypothesisH1Draft,
    *,
    context: InitialFiscalHypothesisContext,
    provider_name: str,
    model_name: str,
) -> FiscalHypothesisH1Result:
    """Confina H1 al contexto temprano y evita que anticipe autoridad jurídica."""

    allowed_facts = {(item.name, item.value, item.origin.value) for item in context.facts}
    invalid_facts = [
        item
        for item in draft.facts_used
        if (item.name, item.value, item.origin.value) not in allowed_facts
    ]
    if invalid_facts:
        raise HybridHypothesisValidationError(
            "H1 intentó utilizar hechos fuera del contexto temprano autorizado."
        )

    allowed_institutions = {
        value
        for value in (
            context.heuristic_route.primary_institution_id,
            context.heuristic_route.primary_institution_label,
        )
        if value
    }
    if any(item not in allowed_institutions for item in draft.institutions):
        raise HybridHypothesisValidationError(
            "H1 intentó introducir una institución no proporcionada por la ruta heurística."
        )

    allowed_norms = set(context.heuristic_route.exact_normative_hints)
    if any(item not in allowed_norms for item in draft.candidate_normative_refs):
        raise HybridHypothesisValidationError(
            "H1 intentó introducir una referencia normativa fuera de las pistas autorizadas."
        )

    if _contains_explicit_authority_citation(draft.proposition):
        raise HybridHypothesisValidationError(
            "H1 no puede convertir una cita jurídica específica en afirmación "
            "antes de la validación normativa."
        )

    context_payload = context.model_dump(mode="json")
    context_digest = _canonical_digest(context_payload)
    hypothesis_digest = _canonical_digest(
        {
            "context": context_payload,
            "draft": draft.model_dump(mode="json"),
        }
    )
    controlled = ControlledFiscalHypothesisH1(
        hypothesis_id=f"H1-{hypothesis_digest[:16]}",
        source_context_sha256=context_digest,
        legal_problem=draft.legal_problem,
        proposition=draft.proposition,
        facts_used=list(draft.facts_used),
        institutions=list(draft.institutions),
        candidate_normative_refs=list(draft.candidate_normative_refs),
        candidate_normative_questions=list(draft.candidate_normative_questions),
        assumptions=list(draft.assumptions),
        uncertainties=list(draft.uncertainties),
        confidence=draft.confidence,
        provider_name=provider_name,
        model_name=model_name,
    )
    return FiscalHypothesisH1Result(
        generation_performed=True,
        hypothesis=controlled,
        requires_human_review=(
            context.requires_human_review
            or context.requires_clarification
            or bool(draft.uncertainties)
        ),
        trace=[
            "f3:h1=controlled",
            "f3:h1:phase=initial_fiscal_hypothesis",
            "f3:h1:retrieval_evidence_used=false",
            "f3:h1:rbs_result_used=false",
            "f3:h1:cbr_result_used=false",
            "f3:h1:requires_validation=true",
            "f3:h1:can_control_legal_decision=false",
        ],
    )


def validate_jurisprudential_ratio_h2(
    draft: JurisprudentialRatioH2Draft,
    *,
    context: JurisprudentialRatioContext,
    provider_name: str,
    model_name: str,
) -> JurisprudentialRatioH2Result:
    """Exige que H2 permanezca trazable a Justificación y normas ya identificadas."""

    allowed_norms = set(context.candidate_normative_refs)
    if any(item not in allowed_norms for item in draft.interpreted_norms):
        raise HybridHypothesisValidationError(
            "H2 intentó introducir una norma fuera de las relaciones jurisprudenciales autorizadas."
        )

    if draft.material_facts and not context.facts_text:
        raise HybridHypothesisValidationError(
            "H2 no puede afirmar hechos materiales si la tesis no aporta sección de Hechos."
        )

    justification = _normalize_span(context.justification_text)
    allowed_pages = set(context.justification_source_pages)
    for span in draft.supporting_spans:
        if span.page not in allowed_pages:
            raise HybridHypothesisValidationError(
                "H2 citó una página fuera de la Justificación autorizada."
            )
        normalized = _normalize_span(span.text)
        if normalized not in justification:
            raise HybridHypothesisValidationError(
                "H2 intentó usar un fragmento que no pertenece a la Justificación."
            )

    context_payload = context.model_dump(mode="json")
    context_digest = _canonical_digest(context_payload)
    ratio_digest = _canonical_digest(
        {
            "context": context_payload,
            "draft": draft.model_dump(mode="json"),
        }
    )
    controlled = ControlledJurisprudentialRatioH2(
        ratio_id=f"H2-{ratio_digest[:16]}",
        document_id=context.document_id,
        source_sha256=context.source_sha256,
        source_context_sha256=context_digest,
        justification_source_pages=list(context.justification_source_pages),
        legal_question=draft.legal_question,
        material_facts=list(draft.material_facts),
        interpreted_norms=list(draft.interpreted_norms),
        essential_premises=list(draft.essential_premises),
        proposed_ratio=draft.proposed_ratio,
        possible_obiter=list(draft.possible_obiter),
        supporting_spans=list(draft.supporting_spans),
        uncertainties=list(draft.uncertainties),
        confidence=draft.confidence,
        provider_name=provider_name,
        model_name=model_name,
    )
    return JurisprudentialRatioH2Result(
        generation_performed=True,
        ratio=controlled,
        requires_human_review=True,
        trace=[
            "f3:h2=controlled",
            f"f3:h2:document_id={context.document_id}",
            "f3:h2:source_section=justification",
            "f3:h2:ratio_subset_of_justification=true",
            "f3:h2:applicability_evaluated=false",
            "f3:h2:requires_validation=true",
            "f3:h2:can_control_legal_decision=false",
        ],
    )
