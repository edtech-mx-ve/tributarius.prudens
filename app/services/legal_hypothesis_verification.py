from __future__ import annotations

import unicodedata

from app.domain.hybrid_coordination import HybridCoordinationResult
from app.domain.legal_hypothesis import ControlledLegalHypothesisResult
from app.domain.legal_hypothesis_verification import (
    LegalHypothesisVerificationResult,
    LegalHypothesisVerificationState,
)
from app.domain.rules import RuleEvaluationResult


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    return " ".join(
        "".join(
            char for char in normalized if not unicodedata.combining(char)
        ).split()
    )


def _deterministic_conclusions(
    rule_result: RuleEvaluationResult,
    hybrid_coordination: HybridCoordinationResult | None,
) -> tuple[list[str], str | None]:
    if (
        hybrid_coordination is not None
        and hybrid_coordination.conclusion is not None
    ):
        return (
            [hybrid_coordination.conclusion],
            hybrid_coordination.controlling_source,
        )

    conclusions = [
        item.conclusion
        for item in rule_result.matched_rules
        if item.conclusion.strip()
    ]
    return list(dict.fromkeys(conclusions)), ("rbs" if conclusions else None)


def verify_initial_legal_hypothesis(
    initial_hypothesis: ControlledLegalHypothesisResult | None,
    *,
    rule_result: RuleEvaluationResult,
    hybrid_coordination: HybridCoordinationResult | None,
) -> LegalHypothesisVerificationResult:
    """Contrasta la hipótesis con el resultado sin inferir equivalencia semántica.

    El verificador registra el resultado determinista disponible, comprueba que
    las citas de la hipótesis sigan dentro de su frontera autorizada y conserva
    explícitamente que una coincidencia textual no constituye validación jurídica.
    """
    if (
        initial_hypothesis is None
        or not initial_hypothesis.generation_performed
        or initial_hypothesis.hypothesis is None
    ):
        return LegalHypothesisVerificationResult(
            state=LegalHypothesisVerificationState.NOT_APPLICABLE,
            findings=[
                "No existe una hipótesis generativa formulada que deba contrastarse."
            ],
            trace=[
                "legal_hypothesis_verification:state=not_applicable",
                "legal_hypothesis_verification:deterministic_result_preserved=true",
            ],
        )

    hypothesis = initial_hypothesis.hypothesis
    allowed = set(initial_hypothesis.authorized_evidence_ids)
    evidence_preserved = all(
        evidence_id in allowed for evidence_id in hypothesis.evidence_ids
    )

    conclusions, controlling_source = _deterministic_conclusions(
        rule_result,
        hybrid_coordination,
    )
    if not conclusions:
        return LegalHypothesisVerificationResult(
            state=LegalHypothesisVerificationState.INCONCLUSIVE,
            hypothesis_text=hypothesis.hypothesis,
            deterministic_conclusions=[],
            controlling_source=None,
            authorized_evidence_preserved=evidence_preserved,
            exact_text_match=None,
            findings=[
                "No existe una conclusión determinista disponible para el contraste.",
                (
                    "La hipótesis permanece como propuesta no vinculante y no se "
                    "promueve a conclusión jurídica."
                ),
            ],
            trace=[
                "legal_hypothesis_verification:state=inconclusive",
                (
                    "legal_hypothesis_verification:"
                    f"authorized_evidence_preserved={str(evidence_preserved).lower()}"
                ),
                "legal_hypothesis_verification:semantic_equivalence_asserted=false",
                "legal_hypothesis_verification:deterministic_result_preserved=true",
            ],
        )

    folded_hypothesis = _fold(hypothesis.hypothesis)
    exact_match = any(
        folded_hypothesis == _fold(conclusion) for conclusion in conclusions
    )

    findings = [
        "La hipótesis fue contrastada con el resultado jurídico determinista.",
        (
            "La coincidencia textual se registra solo como dato experimental; "
            "no acredita equivalencia ni validez jurídica."
        ),
    ]
    if not evidence_preserved:
        findings.append(
            "La frontera de evidencia autorizada no se preservó en el contraste."
        )

    return LegalHypothesisVerificationResult(
        state=LegalHypothesisVerificationState.COMPARED,
        hypothesis_text=hypothesis.hypothesis,
        deterministic_conclusions=conclusions,
        controlling_source=controlling_source,
        authorized_evidence_preserved=evidence_preserved,
        exact_text_match=exact_match,
        semantic_equivalence_asserted=False,
        deterministic_result_preserved=True,
        findings=findings,
        trace=[
            "legal_hypothesis_verification:state=compared",
            (
                "legal_hypothesis_verification:"
                f"authorized_evidence_preserved={str(evidence_preserved).lower()}"
            ),
            (
                "legal_hypothesis_verification:"
                f"exact_text_match={str(exact_match).lower()}"
            ),
            "legal_hypothesis_verification:semantic_equivalence_asserted=false",
            "legal_hypothesis_verification:deterministic_result_preserved=true",
        ],
    )
