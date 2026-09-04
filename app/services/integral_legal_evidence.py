from __future__ import annotations

from app.domain.integral_legal_evidence import (
    IntegralLegalEvidenceChannel,
    IntegralLegalEvidenceItem,
    IntegralLegalEvidenceMap,
)
from app.domain.orchestration import HybridOrchestrationResult


def _normative(result: HybridOrchestrationResult) -> IntegralLegalEvidenceItem:
    refs = list(result.applicable_normative_refs)
    return IntegralLegalEvidenceItem(
        channel=IntegralLegalEvidenceChannel.NORMATIVE,
        present=bool(refs),
        references=refs,
    )


def _rbs(result: HybridOrchestrationResult) -> IntegralLegalEvidenceItem:
    conclusions = result.rule_result.matched_rules
    refs = [
        f"{item.rule_id}:{item.version}"
        for item in conclusions
    ]
    return IntegralLegalEvidenceItem(
        channel=IntegralLegalEvidenceChannel.RBS,
        present=bool(conclusions),
        references=refs,
        requires_human_review=result.rule_result.requires_human_review,
    )


def _cbr(result: HybridOrchestrationResult) -> IntegralLegalEvidenceItem:
    cbr = result.cbr_result
    if cbr is None:
        return IntegralLegalEvidenceItem(
            channel=IntegralLegalEvidenceChannel.CBR,
            present=False,
        )

    refs = [match.case_id for match in cbr.matches]
    return IntegralLegalEvidenceItem(
        channel=IntegralLegalEvidenceChannel.CBR,
        present=bool(refs),
        references=refs,
        requires_human_review=any(
            match.requires_human_review for match in cbr.matches
        ),
    )


def _jurisprudence(
    result: HybridOrchestrationResult,
) -> IntegralLegalEvidenceItem:
    refs: list[str] = []
    review = False

    jurisprudence = result.jurisprudence_result
    if jurisprudence is not None:
        refs.extend(hit.metadata.identifier for hit in jurisprudence.hits)
        review = review or jurisprudence.requires_human_review

    session = result.session_jurisprudence_result
    if session is not None:
        refs.extend(session.evidence)
        review = review or session.requires_human_review

    return IntegralLegalEvidenceItem(
        channel=IntegralLegalEvidenceChannel.JURISPRUDENCE,
        present=bool(refs),
        references=list(dict.fromkeys(refs)),
        requires_human_review=review,
    )


def _calculation(result: HybridOrchestrationResult) -> IntegralLegalEvidenceItem:
    calculation = result.isr_result
    if calculation is None:
        return IntegralLegalEvidenceItem(
            channel=IntegralLegalEvidenceChannel.CALCULATION,
            present=False,
        )

    return IntegralLegalEvidenceItem(
        channel=IntegralLegalEvidenceChannel.CALCULATION,
        present=True,
        references=[
            calculation.normative_ref,
            calculation.tariff_version,
            calculation.source_reference,
        ],
    )


def build_integral_legal_evidence_map(
    result: HybridOrchestrationResult,
) -> IntegralLegalEvidenceMap:
    """Integra canales existentes sin otorgarles nueva fuerza decisoria."""

    return IntegralLegalEvidenceMap(
        items=[
            _normative(result),
            _rbs(result),
            _cbr(result),
            _jurisprudence(result),
            _calculation(result),
        ]
    )
