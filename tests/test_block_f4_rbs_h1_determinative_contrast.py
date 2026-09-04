from __future__ import annotations

from app.domain.hybrid_coordination import HybridReasoningRelation
from app.domain.hybrid_llama_hypotheses import (
    ControlledFiscalHypothesisH1,
    FiscalHypothesisH1Result,
    H1FactReference,
)
from app.domain.llama_hybrid_context import LlamaHybridContextPhase
from app.domain.orchestration import HybridOrchestrationResult
from app.domain.query import FactOrigin
from app.domain.rbs_h1_contrast import RBSH1ContrastState, RBSH1NormativeAlignment
from app.domain.rules import RuleConclusion, RuleEvaluationResult
from app.services.hybrid_contract_baseline import audit_current_hybrid_contracts
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from app.services.rbs_h1_contrast import contrast_h1_with_rbs
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


def _h1(
    proposition: str,
    *,
    refs: list[str] | None = None,
) -> FiscalHypothesisH1Result:
    hypothesis = ControlledFiscalHypothesisH1(
        hypothesis_id="H1-0123456789abcdef",
        source_context_sha256="a" * 64,
        source_phase=LlamaHybridContextPhase.INITIAL_FISCAL_HYPOTHESIS,
        legal_problem="Determinar el efecto fiscal aplicable.",
        proposition=proposition,
        facts_used=[
            H1FactReference(
                name="fiscal_regime",
                value="RESICO",
                origin=FactOrigin.EXPLICIT,
            )
        ],
        institutions=["resico_personas_fisicas"],
        candidate_normative_refs=refs or [],
        candidate_normative_questions=[],
        assumptions=[],
        uncertainties=[],
        confidence=0.70,
        provider_name="f4-static",
        model_name="llama-f4-test",
    )
    return FiscalHypothesisH1Result(
        generation_performed=True,
        hypothesis=hypothesis,
        requires_human_review=False,
        trace=["f3:h1=controlled"],
    )


def _rules(
    conclusion: str | None,
    *,
    normative_refs: list[str] | None = None,
    rule_id: str = "RBS_TEST_001",
    conclusion_code: str = "test_outcome",
    requires_review: bool = False,
) -> RuleEvaluationResult:
    matched_rules: list[RuleConclusion] = []
    if conclusion is not None:
        matched_rules.append(
            RuleConclusion(
                rule_id=rule_id,
                version="1.0",
                conclusion_code=conclusion_code,
                conclusion=conclusion,
                normative_refs=normative_refs or [],
                source_refs=[],
                requires_human_review=requires_review,
            )
        )
    return RuleEvaluationResult(
        matched_rules=matched_rules,
        traces=[],
        derivations=[],
        requires_human_review=requires_review,
    )


def test_f4_without_h1_is_not_applicable_and_preserves_rbs() -> None:
    result = contrast_h1_with_rbs(
        None,
        rule_result=_rules("Debe abandonar el régimen."),
    )

    assert result.state is RBSH1ContrastState.NOT_APPLICABLE
    assert result.relation is None
    assert result.rbs_conclusions == ["Debe abandonar el régimen."]
    assert result.controlling_source == "rbs"
    assert result.deterministic_result_preserved is True
    assert result.hypothesis_changes_rbs_result is False


def test_f4_no_rbs_conclusion_fails_closed_to_insufficient_evidence() -> None:
    result = contrast_h1_with_rbs(
        _h1("Debe abandonar el régimen."),
        rule_result=_rules(None),
    )

    assert result.state is RBSH1ContrastState.INCONCLUSIVE
    assert result.relation is HybridReasoningRelation.INSUFFICIENT_EVIDENCE
    assert result.controlling_source is None
    assert result.requires_human_review is True


def test_f4_exact_h1_and_rbs_conclusion_confirms_when_normative_basis_aligns() -> None:
    proposition = "Debe abandonar el régimen por exceder el límite aplicable."
    result = contrast_h1_with_rbs(
        _h1(proposition, refs=["lisr:articulo_113_e"]),
        rule_result=_rules(
            proposition,
            normative_refs=["lisr:articulo_113_e"],
        ),
    )

    assert result.state is RBSH1ContrastState.CONTRASTED
    assert result.relation is HybridReasoningRelation.CONFIRMATION
    assert result.normative_alignment is RBSH1NormativeAlignment.ALIGNED
    assert result.shared_normative_refs == ["lisr:articulo_113_e"]
    assert result.exact_text_confirmation is True
    assert result.controlling_source == "rbs"


def test_f4_rbs_corrects_h1_candidate_normative_frame_without_changing_rbs() -> None:
    result = contrast_h1_with_rbs(
        _h1(
            "Debe revisarse la permanencia en el régimen.",
            refs=["cff:articulo_999"],
        ),
        rule_result=_rules(
            "Debe abandonar el régimen.",
            normative_refs=["lisr:articulo_113_e"],
        ),
    )

    assert result.relation is HybridReasoningRelation.CORRECTION
    assert result.normative_alignment is RBSH1NormativeAlignment.DISJOINT
    assert result.shared_normative_refs == []
    assert result.unsupported_h1_normative_refs == ["cff:articulo_999"]
    assert result.rbs_conclusions == ["Debe abandonar el régimen."]
    assert result.hypothesis_changes_rbs_result is False


def test_f4_detects_only_explicit_symmetric_negation_as_contradiction() -> None:
    result = contrast_h1_with_rbs(
        _h1("El contribuyente puede permanecer en el régimen."),
        rule_result=_rules("El contribuyente no puede permanecer en el régimen."),
    )

    assert result.relation is HybridReasoningRelation.CONTRADICTION
    assert result.explicit_negation_conflict is True
    assert result.requires_human_review is True
    assert result.controlling_source == "rbs"


def test_f4_explicit_exception_rule_limits_h1_without_let_h1_override_it() -> None:
    result = contrast_h1_with_rbs(
        _h1("Se aplica la regla general."),
        rule_result=_rules(
            "Excepción aplicable por condición expresa.",
            normative_refs=["lisr:articulo_113_e"],
            rule_id="R_EXC_001",
            conclusion_code="exception_applies",
        ),
    )

    assert result.relation is HybridReasoningRelation.EXCEPTION
    assert result.explicit_exception_rule_ids == ["R_EXC_001"]
    assert result.controlling_source == "rbs"
    assert result.requires_human_review is True
    assert result.can_control_legal_decision is False


def test_f4_does_not_infer_semantic_equivalence_from_partial_text_similarity() -> None:
    result = contrast_h1_with_rbs(
        _h1(
            "El exceso de ingresos puede afectar la permanencia en RESICO.",
            refs=["lisr:articulo_113_e"],
        ),
        rule_result=_rules(
            "Debe abandonar el régimen a partir del periodo correspondiente.",
            normative_refs=["lisr:articulo_113_e"],
        ),
    )

    assert result.relation is HybridReasoningRelation.INSUFFICIENT_EVIDENCE
    assert result.exact_text_confirmation is False
    assert result.explicit_negation_conflict is False
    assert "f4:rbs_h1:semantic_equivalence_inferred=false" in result.trace


def test_f4_rbs_human_review_prevents_false_determinative_classification() -> None:
    result = contrast_h1_with_rbs(
        _h1("Debe abandonar el régimen."),
        rule_result=_rules(
            "Debe abandonar el régimen.",
            requires_review=True,
        ),
    )

    assert result.state is RBSH1ContrastState.INCONCLUSIVE
    assert result.relation is HybridReasoningRelation.INSUFFICIENT_EVIDENCE
    assert result.rbs_requires_human_review is True
    assert result.requires_human_review is True


def test_f4_result_channel_is_additive_and_not_runtime_activated() -> None:
    baseline = _orchestrator(None).run(_request())

    assert "rbs_h1_contrast" in HybridOrchestrationResult.model_fields
    assert baseline.llama_fiscal_hypothesis_h1 is None
    assert baseline.rbs_h1_contrast is None


def test_f4_contrast_object_does_not_change_analyzer_or_legal_decision() -> None:
    baseline = _orchestrator(None).run(_request())
    contrast = contrast_h1_with_rbs(
        _h1("Hipótesis distinta a la salida RBS."),
        rule_result=baseline.rule_result,
    )
    enriched = baseline.model_copy(update={"rbs_h1_contrast": contrast})

    baseline_analysis = build_integral_legal_analysis(baseline)
    enriched_analysis = build_integral_legal_analysis(enriched)
    baseline_decision = build_legal_decision(baseline_analysis)
    enriched_decision = build_legal_decision(enriched_analysis)

    assert enriched_analysis == baseline_analysis
    assert enriched_decision == baseline_decision


def test_f4_preserves_f1_contracts_and_real_llm_remains_inactive() -> None:
    audit = audit_current_hybrid_contracts()

    assert audit.all_contracts_preserved is True
    assert audit.real_llm_activation_performed is False
    assert audit.h1_h2_runtime_activation_performed is False
    assert audit.runtime_order_changed is False
    assert audit.legal_decision_changed is False
