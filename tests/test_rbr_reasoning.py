from app.domain.rules import RuleCondition, RuleDefinition, RuleOperator, RuleSet
from app.services.rbr_reasoning import infer_rule_facts


def _rules() -> RuleSet:
    return RuleSet(
        schema_version="1.0",
        rules=[
            RuleDefinition(
                rule_id="PROFILE_INDIVIDUAL_001",
                version="1.0",
                description="Reconoce el perfil fiscal individual.",
                priority=300,
                conditions=[
                    RuleCondition(
                        fact="taxpayer_type",
                        operator=RuleOperator.EQ,
                        value="individual",
                    )
                ],
                conclusion_code="individual_profile",
                conclusion="El caso corresponde a una persona física.",
                normative_refs=["CFF_PROFILE_REF"],
            ),
            RuleDefinition(
                rule_id="ISR_REVIEW_001",
                version="1.0",
                description="Deriva la revisión de obligaciones ISR desde el perfil.",
                priority=200,
                conditions=[
                    RuleCondition(
                        fact="individual_profile",
                        operator=RuleOperator.EQ,
                        value=True,
                    ),
                    RuleCondition(
                        fact="has_taxable_income",
                        operator=RuleOperator.EQ,
                        value=True,
                    ),
                ],
                conclusion_code="review_isr_obligations",
                conclusion="Deben revisarse las obligaciones de ISR del caso.",
                normative_refs=["LISR_OBLIGATION_REF"],
            ),
        ],
    )


def test_rbr_chains_rule_conclusions_as_new_facts() -> None:
    result = infer_rule_facts(
        _rules(),
        {
            "taxpayer_type": "individual",
            "has_taxable_income": True,
        },
        {"CFF_PROFILE_REF", "LISR_OBLIGATION_REF"},
    )

    assert [item.rule_id for item in result.matched_rules] == [
        "PROFILE_INDIVIDUAL_001",
        "ISR_REVIEW_001",
    ]
    assert [item.conclusion_code for item in result.matched_rules] == [
        "individual_profile",
        "review_isr_obligations",
    ]


def test_rbr_does_not_fire_derived_rule_without_required_norm() -> None:
    result = infer_rule_facts(
        _rules(),
        {
            "taxpayer_type": "individual",
            "has_taxable_income": True,
        },
        {"CFF_PROFILE_REF"},
    )

    assert [item.rule_id for item in result.matched_rules] == ["PROFILE_INDIVIDUAL_001"]
    derived_traces = [
        trace for trace in result.traces if trace.rule_id == "ISR_REVIEW_001"
    ]
    assert derived_traces
    assert all(
        trace.skipped_reason == "Faltan referencias normativas aplicables."
        for trace in derived_traces
    )


def test_rbr_reaches_fixed_point_without_duplicate_conclusions() -> None:
    result = infer_rule_facts(
        _rules(),
        {
            "taxpayer_type": "individual",
            "has_taxable_income": True,
        },
        {"CFF_PROFILE_REF", "LISR_OBLIGATION_REF"},
    )

    keys = [(item.rule_id, item.version) for item in result.matched_rules]
    assert len(keys) == len(set(keys))
    assert len(result.matched_rules) == 2
