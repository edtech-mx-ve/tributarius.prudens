from __future__ import annotations

import hashlib
import json
import unicodedata

from app.domain.cbr_h1_contrast import CBRH1ContrastResult
from app.domain.hybrid_coordination import HybridReasoningRelation
from app.domain.hybrid_legal_coordination import (
    H1CoordinationDisposition,
    HybridLegalCoordinationResult,
    HybridLegalCoordinationState,
)
from app.domain.hybrid_legal_verification import (
    HybridLegalSemanticVerificationDraft,
    HybridLegalVerificationPacket,
    HybridLegalVerificationResult,
    HybridLegalVerificationState,
    HybridSemanticAssessment,
    HybridVerificationCheck,
    HybridVerificationCheckOutcome,
)
from app.domain.hybrid_llama_hypotheses import (
    FiscalHypothesisH1Result,
    JurisprudentialRatioH2Result,
)
from app.domain.jurisprudence_decision_application import (
    JurisprudenceDecisionApplicationRecord,
    JurisprudenceDecisionEffect,
)
from app.domain.llama_hybrid_context import (
    InitialFiscalHypothesisContext,
    JurisprudentialRatioContext,
    PostDeterministicHybridReviewContext,
)
from app.domain.rbs_h1_contrast import RBSH1ContrastResult


def _canonical_digest(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(
        "".join(
            char for char in normalized if not unicodedata.combining(char)
        ).split()
    )


def build_hybrid_legal_verification_packet(
    *,
    coordination: HybridLegalCoordinationResult | None,
    initial_context: InitialFiscalHypothesisContext | None = None,
    h1_result: FiscalHypothesisH1Result | None = None,
    rbs_h1_contrast: RBSH1ContrastResult | None = None,
    cbr_h1_contrast: CBRH1ContrastResult | None = None,
    h2_results: list[JurisprudentialRatioH2Result] | None = None,
    jurisprudence_ratio_contexts: list[JurisprudentialRatioContext] | None = None,
    jurisprudence_application: JurisprudenceDecisionApplicationRecord | None = None,
    post_deterministic_context: PostDeterministicHybridReviewContext | None = None,
) -> HybridLegalVerificationPacket:
    """Construye el snapshot F.7 sin reejecutar ningún subsistema previo."""

    return HybridLegalVerificationPacket(
        coordination=coordination,
        initial_context=initial_context,
        h1_result=h1_result,
        rbs_h1_contrast=rbs_h1_contrast,
        cbr_h1_contrast=cbr_h1_contrast,
        h2_results=list(h2_results or []),
        jurisprudence_ratio_contexts=list(jurisprudence_ratio_contexts or []),
        jurisprudence_application=jurisprudence_application,
        post_deterministic_context=post_deterministic_context,
    )


def hybrid_verification_packet_sha256(packet: HybridLegalVerificationPacket) -> str:
    return _canonical_digest(packet.model_dump(mode="json"))


def _append_check(
    checks: list[HybridVerificationCheck],
    *,
    code: str,
    outcome: HybridVerificationCheckOutcome,
    detail: str,
    refs: list[str] | None = None,
) -> None:
    checks.append(
        HybridVerificationCheck(
            code=code,
            outcome=outcome,
            detail=detail,
            refs=list(refs or []),
        )
    )


def _h1_structural_checks(
    packet: HybridLegalVerificationPacket,
    checks: list[HybridVerificationCheck],
    corrections: list[str],
    reviews: list[str],
) -> tuple[bool | None, bool | None, bool | None, str | None]:
    result = packet.h1_result
    hypothesis = (
        result.hypothesis
        if result is not None and result.generation_performed
        else None
    )
    if hypothesis is None:
        _append_check(
            checks,
            code="h1_not_present",
            outcome=HybridVerificationCheckOutcome.NOT_APPLICABLE,
            detail="No existe H1 generada que deba auditarse.",
        )
        return None, None, None, None

    h1_id = hypothesis.hypothesis_id
    context = packet.initial_context
    if context is None:
        corrections.append("h1_context_missing")
        _append_check(
            checks,
            code="h1_context_missing",
            outcome=HybridVerificationCheckOutcome.FAIL,
            detail="H1 carece del contexto temprano F.2 necesario para verificar trazabilidad.",
            refs=[h1_id],
        )
        context_integrity = False
        facts_ok = False
        norms_ok = False
    else:
        expected_digest = _canonical_digest(context.model_dump(mode="json"))
        context_integrity = hypothesis.source_context_sha256 == expected_digest
        if not context_integrity:
            corrections.append("h1_context_digest_mismatch")
        _append_check(
            checks,
            code="h1_context_integrity",
            outcome=(
                HybridVerificationCheckOutcome.PASS
                if context_integrity
                else HybridVerificationCheckOutcome.FAIL
            ),
            detail=(
                "H1 conserva el hash del contexto temprano autorizado."
                if context_integrity
                else "El hash de contexto de H1 no corresponde al contexto F.2 recibido."
            ),
            refs=[h1_id],
        )

        allowed_facts = {
            (item.name, item.value, item.origin.value) for item in context.facts
        }
        used_facts = {
            (item.name, item.value, item.origin.value) for item in hypothesis.facts_used
        }
        facts_ok = used_facts.issubset(allowed_facts)
        if not facts_ok:
            corrections.append("h1_fact_boundary_violation")
        _append_check(
            checks,
            code="h1_fact_boundary",
            outcome=(
                HybridVerificationCheckOutcome.PASS
                if facts_ok
                else HybridVerificationCheckOutcome.FAIL
            ),
            detail=(
                "Todos los hechos usados por H1 provienen del contexto temprano."
                if facts_ok
                else "H1 contiene uno o más hechos ajenos al contexto temprano autorizado."
            ),
            refs=[h1_id],
        )

        allowed_norms = set(context.heuristic_route.exact_normative_hints)
        used_norms = set(hypothesis.candidate_normative_refs)
        norms_ok = used_norms.issubset(allowed_norms)
        if not norms_ok:
            corrections.append("h1_normative_boundary_violation")
        _append_check(
            checks,
            code="h1_normative_boundary",
            outcome=(
                HybridVerificationCheckOutcome.PASS
                if norms_ok
                else HybridVerificationCheckOutcome.FAIL
            ),
            detail=(
                "Las referencias H1 permanecen dentro de las pistas normativas candidatas F.2."
                if norms_ok
                else "H1 introdujo una referencia normativa fuera de las pistas autorizadas."
            ),
            refs=list(hypothesis.candidate_normative_refs),
        )

    rbs = packet.rbs_h1_contrast
    if rbs is None:
        corrections.append("h1_missing_rbs_contrast")
        _append_check(
            checks,
            code="h1_rbs_contrast",
            outcome=HybridVerificationCheckOutcome.FAIL,
            detail="H1 generada no fue contrastada con RBS en F.4.",
            refs=[h1_id],
        )
    elif rbs.hypothesis_id != h1_id:
        corrections.append("h1_rbs_id_mismatch")
        _append_check(
            checks,
            code="h1_rbs_contrast",
            outcome=HybridVerificationCheckOutcome.FAIL,
            detail="El contraste RBS pertenece a una H1 distinta.",
            refs=[h1_id, str(rbs.hypothesis_id)],
        )
    else:
        _append_check(
            checks,
            code="h1_rbs_contrast",
            outcome=HybridVerificationCheckOutcome.PASS,
            detail="El contraste RBS corresponde a la misma H1.",
            refs=[h1_id],
        )
        if rbs.rbs_requires_human_review:
            reviews.append("rbs_source_requires_human_review")

    cbr = packet.cbr_h1_contrast
    if cbr is None:
        corrections.append("h1_missing_cbr_contrast")
        _append_check(
            checks,
            code="h1_cbr_contrast",
            outcome=HybridVerificationCheckOutcome.FAIL,
            detail="H1 generada no fue contrastada con CBR en F.5.",
            refs=[h1_id],
        )
    elif cbr.hypothesis_id != h1_id:
        corrections.append("h1_cbr_id_mismatch")
        _append_check(
            checks,
            code="h1_cbr_contrast",
            outcome=HybridVerificationCheckOutcome.FAIL,
            detail="El contraste CBR pertenece a una H1 distinta.",
            refs=[h1_id, str(cbr.hypothesis_id)],
        )
    else:
        _append_check(
            checks,
            code="h1_cbr_contrast",
            outcome=HybridVerificationCheckOutcome.PASS,
            detail="El contraste CBR corresponde a la misma H1.",
            refs=[h1_id],
        )

    return context_integrity, facts_ok, norms_ok, h1_id


def _rbs_priority_checks(
    packet: HybridLegalVerificationPacket,
    checks: list[HybridVerificationCheck],
    corrections: list[str],
) -> bool:
    coordination = packet.coordination
    if coordination is None or coordination.canonical_conclusion is None:
        _append_check(
            checks,
            code="rbs_priority",
            outcome=HybridVerificationCheckOutcome.REVIEW,
            detail="No existe conclusión coordinada suficiente para verificar prioridad RBS.",
        )
        return False

    priority_ok = (
        coordination.reasoning_controller == "rbs"
        and coordination.weighted_score_aggregation_used is False
        and coordination.majority_vote_used is False
        and coordination.cbr_can_override_rbs is False
        and coordination.h1_used_as_legal_authority is False
        and coordination.h2_used_as_legal_authority is False
    )

    contrast = packet.rbs_h1_contrast
    if contrast is not None:
        priority_ok = priority_ok and (
            contrast.rbs_authority_preserved
            and contrast.deterministic_result_preserved
            and contrast.hypothesis_changes_rbs_result is False
            and contrast.can_control_legal_decision is False
        )

    if not priority_ok:
        corrections.append("rbs_priority_not_preserved")
    _append_check(
        checks,
        code="rbs_priority",
        outcome=(
            HybridVerificationCheckOutcome.PASS
            if priority_ok
            else HybridVerificationCheckOutcome.FAIL
        ),
        detail=(
            "RBS conserva prioridad determinativa y H1/H2 no controlan el resultado."
            if priority_ok
            else "La cadena híbrida no conserva íntegramente la prioridad determinativa RBS."
        ),
    )

    if packet.h1_result is not None and packet.h1_result.generation_performed:
        hypothesis = packet.h1_result.hypothesis
        if hypothesis is not None and packet.rbs_h1_contrast is not None:
            mapping = {
                HybridReasoningRelation.CONFIRMATION: H1CoordinationDisposition.CONFIRMED,
                HybridReasoningRelation.CORRECTION: H1CoordinationDisposition.CORRECTED,
                HybridReasoningRelation.CONTRADICTION: H1CoordinationDisposition.CONTRADICTED,
                HybridReasoningRelation.EXCEPTION: H1CoordinationDisposition.LIMITED_BY_EXCEPTION,
                HybridReasoningRelation.INSUFFICIENT_EVIDENCE: H1CoordinationDisposition.UNRESOLVED,
                HybridReasoningRelation.HUMAN_REVIEW: H1CoordinationDisposition.UNRESOLVED,
            }
            relation = packet.rbs_h1_contrast.relation
            expected = mapping.get(relation) if relation is not None else None
            disposition_ok = (
                coordination.h1_hypothesis_id == hypothesis.hypothesis_id
                and coordination.rbs_h1_relation is relation
                and coordination.h1_disposition is expected
            )
            if not disposition_ok:
                corrections.append("f6_h1_disposition_mismatch")
            _append_check(
                checks,
                code="f6_h1_disposition",
                outcome=(
                    HybridVerificationCheckOutcome.PASS
                    if disposition_ok
                    else HybridVerificationCheckOutcome.FAIL
                ),
                detail=(
                    "F.6 conserva la disposición H1 derivada del contraste RBS."
                    if disposition_ok
                    else "F.6 no refleja correctamente la relación RBS-H1 recibida."
                ),
                refs=[hypothesis.hypothesis_id],
            )

    return priority_ok


def _cbr_role_checks(
    packet: HybridLegalVerificationPacket,
    checks: list[HybridVerificationCheck],
    corrections: list[str],
) -> bool:
    cbr = packet.cbr_h1_contrast
    coordination = packet.coordination
    if cbr is None:
        if packet.h1_result is not None and packet.h1_result.generation_performed:
            _append_check(
                checks,
                code="cbr_experiential_role",
                outcome=HybridVerificationCheckOutcome.FAIL,
                detail="F.7 no puede verificar el papel CBR porque falta el contraste F.5.",
            )
            return False
        _append_check(
            checks,
            code="cbr_experiential_role",
            outcome=HybridVerificationCheckOutcome.NOT_APPLICABLE,
            detail="No existe H1 y, por tanto, no se requiere contraste CBR-H1.",
        )
        return True

    role_ok = (
        cbr.cbr_is_experiential_support
        and cbr.cbr_is_normative_authority is False
        and cbr.cbr_is_jurisprudence is False
        and cbr.cbr_votes_against_rbs is False
        and cbr.rbs_result_used is False
        and cbr.hypothesis_changes_cbr_result is False
        and cbr.can_control_legal_decision is False
    )
    if coordination is not None:
        role_ok = role_ok and coordination.cbr_can_override_rbs is False
        if coordination.cbr_h1_effect is not cbr.effect:
            role_ok = False

    if not role_ok:
        corrections.append("cbr_role_violation")
    _append_check(
        checks,
        code="cbr_experiential_role",
        outcome=(
            HybridVerificationCheckOutcome.PASS
            if role_ok
            else HybridVerificationCheckOutcome.FAIL
        ),
        detail=(
            "CBR permanece como contraste experiencial, no como norma ni jurisprudencia."
            if role_ok
            else "CBR fue representado de forma incompatible con su función experiencial."
        ),
    )
    return role_ok


def _h2_checks(
    packet: HybridLegalVerificationPacket,
    checks: list[HybridVerificationCheck],
    corrections: list[str],
) -> tuple[bool | None, bool | None, list[str]]:
    generated = [
        item.ratio
        for item in packet.h2_results
        if item.generation_performed and item.ratio is not None
    ]
    if not generated:
        _append_check(
            checks,
            code="h2_not_present",
            outcome=HybridVerificationCheckOutcome.NOT_APPLICABLE,
            detail="No existe H2 generada que deba revalidarse.",
        )
        return None, None, []

    contexts = {item.document_id: item for item in packet.jurisprudence_ratio_contexts}
    coordination_links = {
        item.ratio_id: item
        for item in (packet.coordination.h2_links if packet.coordination is not None else [])
    }
    all_source_ok = True
    all_norms_ok = True
    ratio_ids: list[str] = []

    for ratio in generated:
        ratio_ids.append(ratio.ratio_id)
        context = contexts.get(ratio.document_id)
        source_ok = context is not None
        norms_ok = context is not None

        if context is not None:
            expected_digest = _canonical_digest(context.model_dump(mode="json"))
            source_ok = source_ok and ratio.source_context_sha256 == expected_digest
            source_ok = source_ok and ratio.source_sha256 == context.source_sha256
            source_ok = source_ok and ratio.justification_source_pages == list(
                context.justification_source_pages
            )
            justification = _normalize_text(context.justification_text)
            allowed_pages = set(context.justification_source_pages)
            for span in ratio.supporting_spans:
                source_ok = source_ok and span.page in allowed_pages
                source_ok = source_ok and _normalize_text(span.text) in justification
            norms_ok = set(ratio.interpreted_norms).issubset(
                set(context.candidate_normative_refs)
            )

        link = coordination_links.get(ratio.ratio_id)
        source_ok = source_ok and link is not None
        if link is not None:
            source_ok = source_ok and link.document_id == ratio.document_id
            source_ok = source_ok and link.ratio_source_is_justification
            source_ok = source_ok and link.h2_used_as_legal_authority is False

        all_source_ok = all_source_ok and source_ok
        all_norms_ok = all_norms_ok and norms_ok

        if not source_ok:
            corrections.append(f"h2_source_fidelity_violation:{ratio.ratio_id}")
        if not norms_ok:
            corrections.append(f"h2_normative_boundary_violation:{ratio.ratio_id}")
        _append_check(
            checks,
            code="h2_source_fidelity",
            outcome=(
                HybridVerificationCheckOutcome.PASS
                if source_ok
                else HybridVerificationCheckOutcome.FAIL
            ),
            detail=(
                "H2 permanece anclada a la Justificación, sus páginas y su vínculo F.6."
                if source_ok
                else "H2 perdió trazabilidad con la Justificación o con su vínculo F.6."
            ),
            refs=[ratio.ratio_id, ratio.document_id],
        )
        _append_check(
            checks,
            code="h2_normative_boundary",
            outcome=(
                HybridVerificationCheckOutcome.PASS
                if norms_ok
                else HybridVerificationCheckOutcome.FAIL
            ),
            detail=(
                "Las normas interpretadas por H2 pertenecen al contexto jurisprudencial autorizado."
                if norms_ok
                else (
                    "H2 contiene una norma no autorizada por las relaciones "
                    "jurisprudenciales previas."
                )
            ),
            refs=[ratio.ratio_id, *ratio.interpreted_norms],
        )

    return all_source_ok, all_norms_ok, ratio_ids


def _jurisprudence_checks(
    packet: HybridLegalVerificationPacket,
    checks: list[HybridVerificationCheck],
    corrections: list[str],
    reviews: list[str],
) -> bool:
    coordination = packet.coordination
    application = packet.jurisprudence_application
    if coordination is None:
        _append_check(
            checks,
            code="binding_jurisprudence",
            outcome=HybridVerificationCheckOutcome.REVIEW,
            detail="No existe coordinación F.6 para verificar el efecto jurisprudencial.",
        )
        return False

    applicable_docs = list(application.applicable_document_ids) if application is not None else []
    binding_refs = list(application.binding_evidence_refs) if application is not None else []
    expected_binding = bool(applicable_docs)

    if application is not None and any(
        item.decision_effect is JurisprudenceDecisionEffect.REVIEW_REQUIRED
        for item in application.assessments
    ):
        reviews.append("e6_jurisprudence_applicability_unresolved")

    respected: bool = bool(
        coordination.normative_basis_preserved
        and coordination.jurisprudence_replaces_normative_basis is False
        and coordination.jurisprudence_creates_second_conclusion is False
        and coordination.single_conclusion_preserved
    )

    if expected_binding:
        respected = respected and (
            coordination.jurisprudence_effect
            is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
            and coordination.binding_interpretation_required
            and coordination.binding_jurisprudence_document_ids == applicable_docs
            and coordination.binding_jurisprudence_evidence_refs == binding_refs
        )
    else:
        respected = respected and (
            coordination.binding_interpretation_required is False
            and coordination.binding_jurisprudence_document_ids == []
        )

    if not respected:
        corrections.append("binding_jurisprudence_not_preserved")
    _append_check(
        checks,
        code="binding_jurisprudence",
        outcome=(
            HybridVerificationCheckOutcome.PASS
            if respected
            else HybridVerificationCheckOutcome.FAIL
        ),
        detail=(
            "F.6 preserva la base normativa y el efecto jurisprudencial E.6 sin segunda conclusión."
            if respected
            else "El efecto jurisprudencial E.6 no fue preservado correctamente en F.6."
        ),
        refs=[*applicable_docs, *binding_refs],
    )
    return respected


def _post_context_check(
    packet: HybridLegalVerificationPacket,
    checks: list[HybridVerificationCheck],
    corrections: list[str],
) -> None:
    context = packet.post_deterministic_context
    coordination = packet.coordination
    if context is None or coordination is None:
        return
    compatible = (
        context.hybrid_conclusion == coordination.canonical_conclusion
        and set(context.applicable_normative_refs)
        == set(coordination.applicable_normative_refs)
        and context.legal_decision_included is False
        and context.can_change_deterministic_result is False
    )
    if not compatible:
        corrections.append("post_deterministic_context_mismatch")
    _append_check(
        checks,
        code="post_deterministic_context",
        outcome=(
            HybridVerificationCheckOutcome.PASS
            if compatible
            else HybridVerificationCheckOutcome.FAIL
        ),
        detail=(
            "El contexto posterior F.2 representa la misma conclusión y base normativa F.6."
            if compatible
            else "El contexto posterior F.2 diverge de la coordinación F.6 recibida."
        ),
    )


def validate_semantic_verification_draft(
    packet: HybridLegalVerificationPacket,
    draft: HybridLegalSemanticVerificationDraft,
) -> list[str]:
    """Valida que el verificador generativo sólo evalúe objetos del packet F.7."""

    failures: list[str] = []
    expected_sha = hybrid_verification_packet_sha256(packet)
    if draft.packet_sha256 != expected_sha:
        failures.append("semantic_packet_digest_mismatch")

    h1_present = bool(
        packet.h1_result is not None
        and packet.h1_result.generation_performed
        and packet.h1_result.hypothesis is not None
    )
    if h1_present and draft.h1_consistency is HybridSemanticAssessment.NOT_APPLICABLE:
        failures.append("semantic_h1_missing_assessment")
    if not h1_present and draft.h1_consistency is not HybridSemanticAssessment.NOT_APPLICABLE:
        failures.append("semantic_h1_assessed_without_h1")

    generated_ratio_ids = {
        item.ratio.ratio_id
        for item in packet.h2_results
        if item.generation_performed and item.ratio is not None
    }
    draft_ratio_ids = {item.ratio_id for item in draft.h2_assessments}
    if draft_ratio_ids != generated_ratio_ids:
        failures.append("semantic_h2_assessment_set_mismatch")

    binding = bool(
        packet.jurisprudence_application is not None
        and packet.jurisprudence_application.applicable_document_ids
    )
    if binding and (
        draft.binding_jurisprudence_consistency
        is HybridSemanticAssessment.NOT_APPLICABLE
    ):
        failures.append("semantic_binding_jurisprudence_missing_assessment")
    if not binding and (
        draft.binding_jurisprudence_consistency
        is not HybridSemanticAssessment.NOT_APPLICABLE
    ):
        failures.append("semantic_binding_jurisprudence_assessed_without_binding_effect")

    return failures


def _semantic_checks(
    packet: HybridLegalVerificationPacket,
    draft: HybridLegalSemanticVerificationDraft | None,
    checks: list[HybridVerificationCheck],
    corrections: list[str],
    reviews: list[str],
) -> None:
    coordination = packet.coordination
    semantic_required = bool(
        coordination is not None and coordination.verification_required
    )
    if not semantic_required and draft is None:
        _append_check(
            checks,
            code="semantic_verification",
            outcome=HybridVerificationCheckOutcome.NOT_APPLICABLE,
            detail="F.6 no exige verificación semántica adicional para este resultado.",
        )
        return

    if draft is None:
        reviews.append("semantic_verification_pending")
        _append_check(
            checks,
            code="semantic_verification",
            outcome=HybridVerificationCheckOutcome.REVIEW,
            detail=(
                "F.6 exige verificación semántica, pero todavía no existe salida del "
                "verificador controlado F.7."
            ),
        )
        return

    validation_failures = validate_semantic_verification_draft(packet, draft)
    if validation_failures:
        corrections.extend(validation_failures)
        _append_check(
            checks,
            code="semantic_verification_contract",
            outcome=HybridVerificationCheckOutcome.FAIL,
            detail="La salida semántica F.7 no corresponde exactamente al packet auditado.",
            refs=validation_failures,
        )
        return

    assessments = [
        draft.h1_consistency,
        draft.rbs_representation,
        draft.cbr_role,
        draft.binding_jurisprudence_consistency,
        *[item.source_fidelity for item in draft.h2_assessments],
        *[
            item.consistency_with_coordinated_argument
            for item in draft.h2_assessments
        ],
    ]
    if any(item is HybridSemanticAssessment.INCONSISTENT for item in assessments):
        corrections.append("semantic_inconsistency_detected")
    if any(item is HybridSemanticAssessment.UNRESOLVED for item in assessments):
        reviews.append("semantic_consistency_unresolved")
    if draft.contradiction_codes:
        reviews.append("semantic_contradiction_reported")
    if draft.hallucination_signals:
        reviews.append("semantic_hallucination_signal_reported")
    if draft.requires_human_review:
        reviews.append("semantic_verifier_requests_human_review")

    outcome = HybridVerificationCheckOutcome.PASS
    detail = "El verificador controlado no detectó inconsistencias ni incertidumbres pendientes."
    if "semantic_inconsistency_detected" in corrections:
        outcome = HybridVerificationCheckOutcome.FAIL
        detail = "El verificador controlado detectó una inconsistencia que exige corrección."
    elif any(code.startswith("semantic_") for code in reviews):
        outcome = HybridVerificationCheckOutcome.REVIEW
        detail = "El verificador controlado dejó una incertidumbre o señal para revisión humana."
    _append_check(
        checks,
        code="semantic_verification",
        outcome=outcome,
        detail=detail,
        refs=[*draft.contradiction_codes, *draft.hallucination_signals],
    )


def verify_hybrid_legal_argument(
    packet: HybridLegalVerificationPacket,
    *,
    semantic_draft: HybridLegalSemanticVerificationDraft | None = None,
    semantic_verifier_provider: str | None = None,
    semantic_verifier_model: str | None = None,
) -> HybridLegalVerificationResult:
    """Audita F.1-F.6 sin reejecutar ni modificar ningún resultado previo."""

    checks: list[HybridVerificationCheck] = []
    corrections: list[str] = []
    reviews: list[str] = []
    packet_sha = hybrid_verification_packet_sha256(packet)
    coordination = packet.coordination

    if coordination is None:
        reviews.append("f6_coordination_missing")
        _append_check(
            checks,
            code="f6_coordination",
            outcome=HybridVerificationCheckOutcome.REVIEW,
            detail="No existe coordinación F.6 que permita cerrar la verificación.",
        )
    elif coordination.state is HybridLegalCoordinationState.NOT_READY:
        reviews.append("f6_coordination_not_ready")
        _append_check(
            checks,
            code="f6_coordination",
            outcome=HybridVerificationCheckOutcome.REVIEW,
            detail="F.6 está NOT_READY y no ofrece una conclusión canónica verificable.",
        )
    else:
        _append_check(
            checks,
            code="f6_coordination",
            outcome=HybridVerificationCheckOutcome.PASS,
            detail="La coordinación F.6 contiene una conclusión canónica previa.",
        )

    normative_basis = bool(
        coordination is not None
        and coordination.canonical_conclusion is not None
        and coordination.legal_authority_source == "normative_evidence"
        and coordination.applicable_normative_refs
        and coordination.normative_basis_preserved
    )
    if (
        coordination is not None
        and coordination.canonical_conclusion is not None
        and not normative_basis
    ):
        corrections.append("normative_basis_not_preserved")
    _append_check(
        checks,
        code="normative_basis",
        outcome=(
            HybridVerificationCheckOutcome.PASS
            if normative_basis
            else (
                HybridVerificationCheckOutcome.NOT_APPLICABLE
                if coordination is None or coordination.canonical_conclusion is None
                else HybridVerificationCheckOutcome.FAIL
            )
        ),
        detail=(
            "La conclusión canónica conserva evidencia normativa aplicable como autoridad."
            if normative_basis
            else (
                "No fue posible verificar una base normativa aplicable para la "
                "conclusión canónica."
            )
        ),
        refs=(list(coordination.applicable_normative_refs) if coordination is not None else []),
    )

    h1_context_ok, h1_facts_ok, h1_norms_ok, h1_id = _h1_structural_checks(
        packet,
        checks,
        corrections,
        reviews,
    )
    rbs_priority = _rbs_priority_checks(packet, checks, corrections)
    cbr_role = _cbr_role_checks(packet, checks, corrections)
    h2_source_ok, h2_norms_ok, h2_ids = _h2_checks(packet, checks, corrections)
    binding_respected = _jurisprudence_checks(packet, checks, corrections, reviews)
    _post_context_check(packet, checks, corrections)
    _semantic_checks(packet, semantic_draft, checks, corrections, reviews)

    single_conclusion = bool(
        coordination is not None
        and coordination.single_conclusion_preserved
        and coordination.jurisprudence_creates_second_conclusion is False
        and coordination.can_control_legal_decision is False
    )
    if coordination is not None and not single_conclusion:
        corrections.append("single_conclusion_not_preserved")
    _append_check(
        checks,
        code="single_conclusion",
        outcome=(
            HybridVerificationCheckOutcome.PASS
            if single_conclusion
            else (
                HybridVerificationCheckOutcome.NOT_APPLICABLE
                if coordination is None
                else HybridVerificationCheckOutcome.FAIL
            )
        ),
        detail=(
            "La cadena F.3-F.7 preserva una sola conclusión canónica."
            if single_conclusion
            else "La unicidad de conclusión jurídica no pudo verificarse."
        ),
    )

    corrections = list(dict.fromkeys(corrections))
    reviews = list(dict.fromkeys(reviews))
    if corrections:
        state = HybridLegalVerificationState.CORRECTION_REQUIRED
        requires_human_review = True
    elif reviews:
        state = HybridLegalVerificationState.HUMAN_REVIEW
        requires_human_review = True
    else:
        state = HybridLegalVerificationState.VERIFIED
        requires_human_review = False

    trace = [
        f"f7:state={state.value}",
        f"f7:packet_sha256={packet_sha}",
        "f7:h1_generation_reexecuted=false",
        "f7:h2_generation_reexecuted=false",
        "f7:rbs_reexecuted=false",
        "f7:cbr_reexecuted=false",
        "f7:e6_application_recomputed=false",
        "f7:facts_mutated=false",
        "f7:normative_refs_mutated=false",
        "f7:ratio_mutated=false",
        "f7:canonical_conclusion_mutated=false",
        "f7:creates_second_conclusion=false",
        "f7:can_control_legal_decision=false",
        "f7:semantic_equivalence_inferred_deterministically=false",
    ]
    if semantic_draft is not None:
        trace.append("f7:semantic_verification_performed=true")

    return HybridLegalVerificationResult(
        state=state,
        packet_sha256=packet_sha,
        canonical_conclusion=(
            coordination.canonical_conclusion if coordination is not None else None
        ),
        h1_hypothesis_id=h1_id,
        h2_ratio_ids=h2_ids,
        checks=checks,
        h1_context_integrity_verified=h1_context_ok,
        h1_fact_boundary_verified=h1_facts_ok,
        h1_normative_boundary_verified=h1_norms_ok,
        rbs_priority_preserved=rbs_priority,
        cbr_experiential_role_preserved=cbr_role,
        h2_source_fidelity_verified=h2_source_ok,
        h2_normative_boundary_verified=h2_norms_ok,
        binding_jurisprudence_respected=binding_respected,
        normative_basis_preserved=normative_basis,
        single_conclusion_preserved=single_conclusion,
        semantic_verification_performed=semantic_draft is not None,
        semantic_verifier_provider=(
            semantic_verifier_provider if semantic_draft is not None else None
        ),
        semantic_verifier_model=(semantic_verifier_model if semantic_draft is not None else None),
        semantic_draft=semantic_draft,
        correction_codes=corrections,
        review_codes=reviews,
        requires_human_review=requires_human_review,
        trace=trace,
    )
