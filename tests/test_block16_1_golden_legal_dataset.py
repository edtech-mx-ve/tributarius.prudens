from __future__ import annotations

from app.domain.golden_legal_case import GoldenCaseCategory
from app.services.golden_legal_dataset import load_golden_legal_cases


def test_block16_1_golden_dataset_loads_and_has_unique_ids() -> None:
    cases = load_golden_legal_cases()
    assert len(cases) == 16
    assert len({case.case_id for case in cases}) == len(cases)


def test_block16_1_preserves_all_existing_retrieval_eval_seeds() -> None:
    cases = load_golden_legal_cases()
    source_ids = {case.source_case_id for case in cases if case.source_case_id}
    assert source_ids == {
        "prodecon_derechos",
        "unam_interpretacion",
        "cpeum_principios",
        "cff_rfc",
        "lisr_deducciones_personales",
        "liva_tasa",
        "rmf_2026",
        "lif_2026",
        "lfpca_juicio",
        "lotfja_competencia",
        "lieps",
        "lfisan",
    }


def test_block16_1_does_not_promote_llm_as_allowed_controller() -> None:
    for case in load_golden_legal_cases():
        assert "llm" not in case.expectation.allowed_controlling_sources
        assert "legal_hypothesis" not in case.expectation.allowed_controlling_sources


def test_block16_1_contains_safety_and_adversarial_cases() -> None:
    cases = load_golden_legal_cases()
    categories = {case.category for case in cases}
    assert GoldenCaseCategory.INSUFFICIENT_EVIDENCE in categories
    assert GoldenCaseCategory.ADVERSARIAL in categories


def test_block16_1_safety_cases_require_review_and_no_forced_conclusion() -> None:
    cases = load_golden_legal_cases()
    safety = [
        case
        for case in cases
        if case.category
        in {
            GoldenCaseCategory.INSUFFICIENT_EVIDENCE,
            GoldenCaseCategory.ADVERSARIAL,
        }
    ]
    assert safety
    assert all(case.expectation.requires_human_review is True for case in safety)
    assert all(case.expectation.conclusion_required is False for case in safety)


def test_block16_1_seed_cases_do_not_invent_expert_legal_oracles() -> None:
    cases = load_golden_legal_cases()
    seeded = [case for case in cases if case.source_case_id is not None]
    assert seeded
    assert all(case.expectation.requires_human_review is None for case in seeded)
    assert all(case.expectation.conclusion_required is None for case in seeded)
