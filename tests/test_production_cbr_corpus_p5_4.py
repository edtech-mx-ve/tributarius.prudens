from pathlib import Path

from app.domain.cbr import CaseStatus, CBRQuery
from app.services.cbr_loader import load_cbr_cases_jsonl
from cbr.engine import retrieve_similar_cases

PRODUCTION_CORPUS = Path("cbr/data/production_cases.jsonl")


def test_production_cbr_corpus_loads_two_validated_cases() -> None:
    cases = load_cbr_cases_jsonl(PRODUCTION_CORPUS)

    assert len(cases) == 2
    assert len({case.case_id for case in cases}) == 2
    assert all(case.status is CaseStatus.ACTIVE for case in cases)
    assert all(case.anonymized for case in cases)
    assert all(case.validated for case in cases)


def test_production_cbr_corpus_uses_only_stable_normative_refs() -> None:
    cases = load_cbr_cases_jsonl(PRODUCTION_CORPUS)

    normative_refs = {
        ref
        for case in cases
        for ref in case.normative_refs
    }

    assert normative_refs == {
        "lisr:articulo_100",
        "lisr:articulo_110",
    }


def test_compliance_query_recovers_canonical_professional_case() -> None:
    cases = load_cbr_cases_jsonl(PRODUCTION_CORPUS)

    result = retrieve_similar_cases(
        CBRQuery(
            taxpayer_type="individual",
            activity="servicios profesionales independientes",
            tax="ISR",
            problem_type="cumplimiento_fiscal",
            fiscal_year=2026,
        ),
        cases,
    )

    assert result.returned_count == 1
    assert result.matches[0].case_id == "CASE-TP-ISR-PROF-CUMPL-2026"
    assert result.matches[0].similarity == 1.0


def test_determination_query_recovers_only_determination_case() -> None:
    cases = load_cbr_cases_jsonl(PRODUCTION_CORPUS)

    result = retrieve_similar_cases(
        CBRQuery(
            taxpayer_type="individual",
            activity="servicios profesionales independientes",
            tax="ISR",
            problem_type="determinacion_contribucion",
            fiscal_year=2026,
        ),
        cases,
    )

    assert result.returned_count == 1
    assert result.matches[0].case_id == "CASE-TP-ISR-PROF-DETERM-2026"
    assert result.matches[0].similarity == 1.0


def test_internal_cases_do_not_claim_external_precedent() -> None:
    cases = load_cbr_cases_jsonl(PRODUCTION_CORPUS)

    for case in cases:
        assert "INTERNAL_CANONICAL_CASE:TRIBUTARIUS_PRUDENS" in case.source_refs
        assert "sin caracter de precedente" in case.resolution_summary
