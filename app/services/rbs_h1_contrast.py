from __future__ import annotations

import re
import unicodedata

from app.domain.hybrid_coordination import HybridReasoningRelation
from app.domain.hybrid_llama_hypotheses import FiscalHypothesisH1Result
from app.domain.rbs_h1_contrast import (
    RBSH1ContrastResult,
    RBSH1ContrastState,
    RBSH1NormativeAlignment,
)
from app.domain.rules import RuleEvaluationResult
from app.services.hybrid_reasoning_normalization import normalize_rbs_result


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _fold(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(
        character for character in normalized if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


def _tokens_without_negation(text: str) -> tuple[list[str], bool]:
    tokens = _fold(text).split()
    has_negation = "no" in tokens
    return [token for token in tokens if token != "no"], has_negation


def _explicit_negation_conflict(hypothesis: str, conclusion: str) -> bool:
    """Detecta sólo una contradicción léxica fuerte y simétrica.

    Se exige identidad del texto normalizado al retirar la partícula ``no`` y
    que únicamente una de las dos proposiciones contenga esa negación. Si no
    se cumple, F.4 no presume contradicción semántica.
    """

    h_tokens, h_negated = _tokens_without_negation(hypothesis)
    c_tokens, c_negated = _tokens_without_negation(conclusion)
    return bool(h_tokens) and h_tokens == c_tokens and h_negated != c_negated


def _is_explicit_exception_rule(rule_id: str, conclusion_code: str, conclusion: str) -> bool:
    folded_id = _fold(rule_id)
    folded_code = _fold(conclusion_code)
    folded_conclusion = _fold(conclusion)
    markers = ("exception", "excepcion", "except")
    id_tokens = set(folded_id.split())
    return (
        "exc" in id_tokens
        or any(marker in folded_id for marker in markers)
        or any(marker in folded_code for marker in markers)
        or folded_conclusion.startswith("excepcion ")
    )


def _normative_alignment(
    h1_refs: list[str],
    rbs_refs: list[str],
) -> tuple[RBSH1NormativeAlignment, list[str], list[str]]:
    if not h1_refs:
        return RBSH1NormativeAlignment.NOT_PROPOSED, [], []
    rbs_set = set(rbs_refs)
    shared = [ref for ref in h1_refs if ref in rbs_set]
    unsupported = [ref for ref in h1_refs if ref not in rbs_set]
    if not unsupported:
        return RBSH1NormativeAlignment.ALIGNED, shared, unsupported
    if shared:
        return RBSH1NormativeAlignment.PARTIAL, shared, unsupported
    return RBSH1NormativeAlignment.DISJOINT, shared, unsupported


def contrast_h1_with_rbs(
    h1_result: FiscalHypothesisH1Result | None,
    *,
    rule_result: RuleEvaluationResult,
) -> RBSH1ContrastResult:
    """Contrasta H1 contra el RBS ya ejecutado, sin reejecutar ni alterar reglas.

    La clasificación es deliberadamente conservadora. F.4 sólo afirma
    CONFIRMATION o CONTRADICTION cuando existe una señal textual inequívoca;
    CORRECTION se limita a una divergencia normativa estructurada; EXCEPTION
    exige una regla de excepción explícita. Todo lo demás falla de forma
    cerrada a INSUFFICIENT_EVIDENCE.
    """

    rbs = normalize_rbs_result(rule_result)
    conclusions = _unique([item.conclusion for item in rule_result.matched_rules])
    rule_ids = _unique([item.rule_id for item in rule_result.matched_rules])
    conclusion_codes = _unique(
        [item.conclusion_code for item in rule_result.matched_rules]
    )
    rbs_refs = _unique([ref for item in rule_result.matched_rules for ref in item.normative_refs])
    supporting_facts = _unique(rbs.supporting_facts)
    exception_rules = _unique(
        [
            item.rule_id
            for item in rule_result.matched_rules
            if _is_explicit_exception_rule(
                item.rule_id,
                item.conclusion_code,
                item.conclusion,
            )
        ]
    )

    if (
        h1_result is None
        or not h1_result.generation_performed
        or h1_result.hypothesis is None
    ):
        return RBSH1ContrastResult(
            state=RBSH1ContrastState.NOT_APPLICABLE,
            rbs_conclusions=conclusions,
            matched_rule_ids=rule_ids,
            matched_conclusion_codes=conclusion_codes,
            rbs_normative_refs=rbs_refs,
            rbs_supporting_fact_names=supporting_facts,
            explicit_exception_rule_ids=exception_rules,
            rbs_requires_human_review=rule_result.requires_human_review,
            controlling_source="rbs" if conclusions else None,
            reasons=["No existe H1 controlada que deba contrastarse con el RBS."],
            trace=[
                "f4:rbs_h1:state=not_applicable",
                "f4:rbs_h1:deterministic_result_preserved=true",
                "f4:rbs_h1:hypothesis_changes_rbs_result=false",
            ],
        )

    hypothesis = h1_result.hypothesis
    h1_refs = _unique(hypothesis.candidate_normative_refs)
    h1_fact_names = _unique([fact.name for fact in hypothesis.facts_used])
    shared_facts = [name for name in h1_fact_names if name in set(supporting_facts)]
    alignment, shared_refs, unsupported_refs = _normative_alignment(h1_refs, rbs_refs)

    if not conclusions:
        relation = HybridReasoningRelation.INSUFFICIENT_EVIDENCE
        state = RBSH1ContrastState.INCONCLUSIVE
        reasons = [
            "El RBS no produjo una conclusión determinativa con la cual contrastar H1."
        ]
        review = True
        exact_match: bool | None = None
        negation_conflict: bool | None = None
    elif rule_result.requires_human_review:
        relation = HybridReasoningRelation.INSUFFICIENT_EVIDENCE
        state = RBSH1ContrastState.INCONCLUSIVE
        reasons = [
            "El RBS produjo salida, pero exige revisión humana y F.4 no la promueve a "
            "contraste determinativo definitivo."
        ]
        review = True
        exact_match = None
        negation_conflict = None
    else:
        exact_match = any(
            _fold(hypothesis.proposition) == _fold(conclusion)
            for conclusion in conclusions
        )
        negation_conflict = any(
            _explicit_negation_conflict(hypothesis.proposition, conclusion)
            for conclusion in conclusions
        )
        state = RBSH1ContrastState.CONTRASTED
        review = False

        if exception_rules:
            relation = HybridReasoningRelation.EXCEPTION
            reasons = [
                "El RBS activó una regla identificada explícitamente como excepción; "
                "H1 queda limitada por esa excepción determinativa."
            ]
            review = True
        elif negation_conflict:
            relation = HybridReasoningRelation.CONTRADICTION
            reasons = [
                "H1 y una conclusión RBS presentan una contradicción léxica explícita "
                "con la misma proposición y polaridad opuesta."
            ]
            review = True
        elif exact_match and alignment in {
            RBSH1NormativeAlignment.ALIGNED,
            RBSH1NormativeAlignment.NOT_PROPOSED,
        }:
            relation = HybridReasoningRelation.CONFIRMATION
            reasons = [
                "H1 coincide exactamente con una conclusión RBS y no presenta una "
                "divergencia normativa estructurada."
            ]
        elif alignment in {
            RBSH1NormativeAlignment.PARTIAL,
            RBSH1NormativeAlignment.DISJOINT,
        }:
            relation = HybridReasoningRelation.CORRECTION
            reasons = [
                "El RBS corrige el encuadre normativo candidato de H1 porque una o más "
                "referencias propuestas no sustentan las reglas efectivamente activadas."
            ]
        else:
            relation = HybridReasoningRelation.INSUFFICIENT_EVIDENCE
            reasons = [
                "El RBS produjo una conclusión, pero F.4 no presume equivalencia ni "
                "contradicción semántica a partir de similitud textual parcial."
            ]

    trace = [
        f"f4:rbs_h1:state={state.value}",
        f"f4:rbs_h1:relation={relation.value}",
        f"f4:rbs_h1:normative_alignment={alignment.value}",
        f"f4:rbs_h1:rbs_conclusions={len(conclusions)}",
        f"f4:rbs_h1:shared_normative_refs={len(shared_refs)}",
        f"f4:rbs_h1:unsupported_h1_normative_refs={len(unsupported_refs)}",
        f"f4:rbs_h1:shared_fact_names={len(shared_facts)}",
        "f4:rbs_h1:rbs_reexecuted=false",
        "f4:rbs_h1:semantic_equivalence_inferred=false",
        "f4:rbs_h1:deterministic_result_preserved=true",
        "f4:rbs_h1:hypothesis_changes_rbs_result=false",
        "f4:rbs_h1:can_control_legal_decision=false",
    ]

    return RBSH1ContrastResult(
        state=state,
        hypothesis_id=hypothesis.hypothesis_id,
        relation=relation,
        h1_proposition=hypothesis.proposition,
        rbs_conclusions=conclusions,
        matched_rule_ids=rule_ids,
        matched_conclusion_codes=conclusion_codes,
        h1_candidate_normative_refs=h1_refs,
        rbs_normative_refs=rbs_refs,
        shared_normative_refs=shared_refs,
        unsupported_h1_normative_refs=unsupported_refs,
        normative_alignment=alignment,
        h1_fact_names=h1_fact_names,
        rbs_supporting_fact_names=supporting_facts,
        shared_fact_names=shared_facts,
        explicit_exception_rule_ids=exception_rules,
        exact_text_confirmation=exact_match,
        explicit_negation_conflict=negation_conflict,
        rbs_requires_human_review=rule_result.requires_human_review,
        controlling_source="rbs" if conclusions else None,
        deterministic_result_preserved=True,
        hypothesis_changes_rbs_result=False,
        can_control_legal_decision=False,
        reasons=reasons,
        requires_human_review=review,
        trace=trace,
    )
