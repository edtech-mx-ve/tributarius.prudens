from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_rbs_benchmark import (
    PrimaryRBSBenchmarkCase,
    PrimaryRBSBenchmarkCaseResult,
    PrimaryRBSBenchmarkReport,
    PrimaryRBSBenchmarkSuite,
)
from app.domain.primary_rbs_corpus_validation import PrimaryRBSCorpusValidationReport
from app.domain.primary_rbs_deduplication import PrimaryRBSDeduplicationMap
from app.domain.primary_rbs_existing_integration import ExistingRBSRuleIntegrationMap
from app.domain.primary_rbs_inventory import CurrentRBSInventory
from app.services.primary_rbs_existing_integration import (
    infer_integrated_existing_rule_facts,
    validate_existing_rbs_rule_integration,
)


class PrimaryRBSBenchmarkError(RuntimeError):
    """Error controlado del benchmark RBS B.10."""


def load_primary_rbs_benchmark_suite(path: Path) -> PrimaryRBSBenchmarkSuite:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryRBSBenchmarkError(
            f"No existe el benchmark RBS B.10: {resolved}"
        )
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryRBSBenchmarkSuite.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryRBSBenchmarkError(
            "El benchmark RBS B.10 no es válido."
        ) from exc


def validate_primary_rbs_benchmark_suite(
    suite: PrimaryRBSBenchmarkSuite,
    integration_map: ExistingRBSRuleIntegrationMap,
    inventory: CurrentRBSInventory,
    deduplication: PrimaryRBSDeduplicationMap,
    corpus_validation: PrimaryRBSCorpusValidationReport,
) -> None:
    """Valida cobertura y frontera del benchmark antes de ejecutarlo."""
    validate_existing_rbs_rule_integration(
        integration_map,
        inventory,
        deduplication,
        corpus_validation,
    )

    integrated_rule_ids = {
        item.rule_id for item in integration_map.integrations
    }
    if set(suite.required_rule_coverage) != integrated_rule_ids:
        raise PrimaryRBSBenchmarkError(
            "B.10 debe exigir cobertura exacta de las 14 reglas integradas en B.9."
        )

    expected_rule_ids = {
        rule_id
        for case in suite.cases
        for rule_id in case.expected_matched_rule_ids
    }
    if expected_rule_ids != integrated_rule_ids:
        raise PrimaryRBSBenchmarkError(
            "Los casos B.10 deben ejercitar las 14 reglas productivas."
        )

    known_normative_refs = {
        ref
        for item in integration_map.integrations
        for ref in item.normative_refs
    }
    for case in suite.cases:
        unknown_rules = (
            set(case.expected_matched_rule_ids)
            | set(case.expected_absent_rule_ids)
        ) - integrated_rule_ids
        if unknown_rules:
            raise PrimaryRBSBenchmarkError(
                f"{case.case_id} referencia reglas fuera de B.9."
            )

        if case.applicable_normative_refs is not None:
            unknown_refs = set(case.applicable_normative_refs) - known_normative_refs
            if unknown_refs:
                raise PrimaryRBSBenchmarkError(
                    f"{case.case_id} usa evidencia normativa ajena a B.9."
                )

        for edge in case.required_derivation_edges:
            if (
                edge.producer_rule_id not in integrated_rule_ids
                or edge.consumer_rule_id not in integrated_rule_ids
            ):
                raise PrimaryRBSBenchmarkError(
                    f"{case.case_id} exige una arista fuera de las reglas B.9."
                )


def _edge_label(
    producer_rule_id: str,
    consumer_rule_id: str,
    fact: str,
) -> str:
    return f"{producer_rule_id}->{consumer_rule_id}:{fact}"


def _evaluate_case(
    *,
    production_dir: Path,
    case: PrimaryRBSBenchmarkCase,
    integration_map: ExistingRBSRuleIntegrationMap,
    inventory: CurrentRBSInventory,
    deduplication: PrimaryRBSDeduplicationMap,
    corpus_validation: PrimaryRBSCorpusValidationReport,
) -> PrimaryRBSBenchmarkCaseResult:
    applicable_refs = (
        None
        if case.applicable_normative_refs is None
        else set(case.applicable_normative_refs)
    )
    execution = infer_integrated_existing_rule_facts(
        production_dir,
        integration_map,
        inventory,
        deduplication,
        corpus_validation,
        case.facts,
        applicable_refs,
    )

    matched_rule_ids = [item.rule_id for item in execution.matched_rules]
    matched_set = set(matched_rule_ids)
    expected_set = set(case.expected_matched_rule_ids)

    missing_rule_ids = sorted(expected_set - matched_set)
    unexpected_rule_ids = sorted(matched_set - expected_set)
    expected_absent_but_matched = sorted(
        matched_set & set(case.expected_absent_rule_ids)
    )

    observed_edges = {
        (
            condition.producer_rule_id,
            derivation.rule_id,
            condition.fact,
        )
        for derivation in execution.derivations
        for condition in derivation.conditions
        if condition.producer_rule_id is not None
    }
    missing_derivation_edges = [
        _edge_label(
            edge.producer_rule_id,
            edge.consumer_rule_id,
            edge.fact,
        )
        for edge in case.required_derivation_edges
        if (
            edge.producer_rule_id,
            edge.consumer_rule_id,
            edge.fact,
        )
        not in observed_edges
    ]

    used_normative_refs = {
        ref
        for derivation in execution.derivations
        for ref in derivation.normative_refs
    }
    authorized_normative_refs = applicable_refs or set()
    unauthorized_normative_refs = sorted(
        used_normative_refs - authorized_normative_refs
    )

    human_review_matches = (
        execution.requires_human_review
        is case.expected_requires_human_review
    )
    traceability_complete = len(execution.derivations) == len(
        execution.matched_rules
    )

    passed = not any(
        (
            missing_rule_ids,
            unexpected_rule_ids,
            expected_absent_but_matched,
            missing_derivation_edges,
            unauthorized_normative_refs,
        )
    ) and human_review_matches and traceability_complete

    return PrimaryRBSBenchmarkCaseResult(
        case_id=case.case_id,
        passed=passed,
        matched_rule_ids=matched_rule_ids,
        missing_rule_ids=missing_rule_ids,
        unexpected_rule_ids=unexpected_rule_ids,
        expected_absent_but_matched=expected_absent_but_matched,
        missing_derivation_edges=missing_derivation_edges,
        unauthorized_normative_refs=unauthorized_normative_refs,
        trace_count=len(execution.traces),
        derivation_count=len(execution.derivations),
        human_review_matches_expectation=human_review_matches,
    )


def run_primary_rbs_benchmark(
    *,
    production_dir: Path,
    suite: PrimaryRBSBenchmarkSuite,
    integration_map: ExistingRBSRuleIntegrationMap,
    inventory: CurrentRBSInventory,
    deduplication: PrimaryRBSDeduplicationMap,
    corpus_validation: PrimaryRBSCorpusValidationReport,
) -> PrimaryRBSBenchmarkReport:
    """Ejecuta el benchmark B.10 sobre el motor integrado existente."""
    validate_primary_rbs_benchmark_suite(
        suite,
        integration_map,
        inventory,
        deduplication,
        corpus_validation,
    )

    results = [
        _evaluate_case(
            production_dir=production_dir,
            case=case,
            integration_map=integration_map,
            inventory=inventory,
            deduplication=deduplication,
            corpus_validation=corpus_validation,
        )
        for case in suite.cases
    ]

    passed_cases = sum(result.passed for result in results)
    pass_rate = passed_cases / len(results)

    covered_rule_ids = sorted(
        {
            rule_id
            for result in results
            for rule_id in result.matched_rule_ids
        }
    )
    required_coverage = set(suite.required_rule_coverage)
    missing_required_rule_coverage = sorted(
        required_coverage - set(covered_rule_ids)
    )
    rule_coverage_rate = (
        len(required_coverage - set(missing_required_rule_coverage))
        / len(required_coverage)
    )

    threshold_met = pass_rate >= suite.pass_threshold
    all_passed = (
        passed_cases == len(results)
        and not missing_required_rule_coverage
        and threshold_met
    )

    return PrimaryRBSBenchmarkReport(
        schema_version="1.0",
        benchmark_version=suite.benchmark_version,
        total_cases=len(results),
        passed_cases=passed_cases,
        pass_rate=pass_rate,
        covered_rule_ids=covered_rule_ids,
        missing_required_rule_coverage=missing_required_rule_coverage,
        rule_coverage_rate=rule_coverage_rate,
        results=results,
        threshold_met=threshold_met,
        all_passed=all_passed,
        validates_current_dataset_only=suite.validates_current_dataset_only,
        claims_full_mexican_tax_law_coverage=(
            suite.claims_full_mexican_tax_law_coverage
        ),
    )
