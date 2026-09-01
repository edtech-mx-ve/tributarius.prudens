from __future__ import annotations

from app.domain.rules import (
    RuleCondition,
    RuleDefinition,
    RuleFactOrigin,
    RuleOperator,
    RuleSet,
)
from app.services.rule_engine import evaluate_rules


def _rules() -> RuleSet:
    return RuleSet(
        schema_version="1.0",
        rules=[
            RuleDefinition(
                rule_id="PROFILE_INDIVIDUAL_001",
                version="1.0.0",
                description="Clasifica persona física.",
                priority=400,
                conditions=[
                    RuleCondition(
                        fact="taxpayer_type",
                        operator=RuleOperator.EQ,
                        value="individual",
                    )
                ],
                conclusion_code="individual_taxpayer_profile",
                conclusion="La persona se clasifica como contribuyente persona física.",
                normative_refs=["cff:articulo_1"],
                source_refs=["CFF artículo 1"],
            ),
            RuleDefinition(
                rule_id="RIGHT_INFORMATION_002",
                version="1.0.0",
                description="Deriva derecho de información.",
                priority=300,
                conditions=[
                    RuleCondition(
                        fact="individual_taxpayer_profile",
                        operator=RuleOperator.EQ,
                        value=True,
                    )
                ],
                conclusion_code="right_information_and_assistance",
                conclusion="Existe derecho de información y asistencia.",
                normative_refs=["lfdc:articulo_2"],
                source_refs=["LFDC artículo 2 fracción I"],
            ),
        ],
    )


def test_derivation_trace_reconstructs_forward_chain() -> None:
    result = evaluate_rules(
        _rules(),
        {"taxpayer_type": "individual"},
        {"cff:articulo_1", "lfdc:articulo_2"},
    )

    assert len(result.derivations) == 2

    profile = result.derivations[0]
    assert profile.sequence == 1
    assert profile.rule_id == "PROFILE_INDIVIDUAL_001"
    assert profile.conditions[0].fact == "taxpayer_type"
    assert profile.conditions[0].origin == RuleFactOrigin.INPUT
    assert profile.conditions[0].producer_rule_id is None
    assert profile.normative_refs == ["cff:articulo_1"]
    assert profile.source_refs == ["CFF artículo 1"]

    right = result.derivations[1]
    assert right.sequence == 2
    assert right.rule_id == "RIGHT_INFORMATION_002"
    assert right.conditions[0].fact == "individual_taxpayer_profile"
    assert right.conditions[0].origin == RuleFactOrigin.INFERRED
    assert right.conditions[0].producer_rule_id == "PROFILE_INDIVIDUAL_001"
    assert right.conditions[0].producer_rule_version == "1.0.0"
    assert right.normative_refs == ["lfdc:articulo_2"]
    assert right.source_refs == ["LFDC artículo 2 fracción I"]


def test_derivation_trace_preserves_cycle_and_conclusion() -> None:
    result = evaluate_rules(
        _rules(),
        {"taxpayer_type": "individual"},
        {"cff:articulo_1", "lfdc:articulo_2"},
    )

    assert [item.cycle for item in result.derivations] == [1, 1]
    assert result.derivations[0].conclusion_code == "individual_taxpayer_profile"
    assert result.derivations[1].conclusion_code == "right_information_and_assistance"


def test_rule_without_normative_support_has_no_derivation() -> None:
    result = evaluate_rules(
        _rules(),
        {"taxpayer_type": "individual"},
        set(),
    )

    assert result.matched_rules == []
    assert result.derivations == []
