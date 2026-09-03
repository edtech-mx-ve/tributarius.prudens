from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.domain.primary_cbr_benchmark import (
    PrimaryCBRBenchmarkCase,
    PrimaryCBRBenchmarkCaseKind,
    PrimaryCBRBenchmarkCaseResult,
    PrimaryCBRBenchmarkReport,
    PrimaryCBRBenchmarkSuite,
)
from app.domain.primary_cbr_corpus_validation import PrimaryCBRCorpusValidationReport
from app.domain.primary_cbr_families import PrimaryCBRFamilyRegistry
from app.domain.primary_cbr_legal_similarity import (
    PrimaryCBRLegalSimilarityDecision,
    PrimaryCBRLegalSimilarityIndex,
)
from app.domain.primary_cbr_levels import PrimaryCBRLevelRegistry
from app.domain.primary_cbr_problem_institution import PrimaryCBRProblemInstitutionClassification
from app.services.primary_cbr_legal_similarity import score_primary_cbr_legal_similarity


class PrimaryCBRBenchmarkError(RuntimeError):
    """Error controlado del benchmark CBR C.11."""


def load_primary_cbr_benchmark_suite(path: Path) -> PrimaryCBRBenchmarkSuite:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise PrimaryCBRBenchmarkError(f"No existe el benchmark CBR C.11: {resolved}")
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        return PrimaryCBRBenchmarkSuite.model_validate(payload)
    except (OSError, UnicodeError, json.JSONDecodeError, ValidationError) as exc:
        raise PrimaryCBRBenchmarkError("El benchmark CBR C.11 no es válido.") from exc


def _assert_global_contract(
    suite: PrimaryCBRBenchmarkSuite,
    classification: PrimaryCBRProblemInstitutionClassification,
    corpus_validation: PrimaryCBRCorpusValidationReport,
    family_registry: PrimaryCBRFamilyRegistry,
    legal_similarity: PrimaryCBRLegalSimilarityIndex,
    level_registry: PrimaryCBRLevelRegistry,
) -> None:
    baselines = {
        suite.baseline_commit,
        classification.baseline_commit,
        corpus_validation.baseline_commit,
        family_registry.baseline_commit,
        legal_similarity.baseline_commit,
        level_registry.baseline_commit,
    }
    if len(baselines) != 1:
        raise PrimaryCBRBenchmarkError("C.11 debe conservar el baseline común C.5-C.10.")

    situation_counts = {
        len(classification.classifications),
        len(corpus_validation.situations),
        len(family_registry.assignments),
        legal_similarity.profile_count,
        level_registry.source_situation_count,
    }
    if situation_counts != {suite.expected_source_situation_count}:
        raise PrimaryCBRBenchmarkError("C.11 perdió cobertura exacta de las situaciones CBR.")

    if level_registry.validated_membership_count != suite.expected_validated_membership_count:
        raise PrimaryCBRBenchmarkError("C.11 detectó cambio en el nivel validado C.10.")
    if level_registry.operational_membership_count != suite.expected_operational_membership_count:
        raise PrimaryCBRBenchmarkError("C.11 detectó cambio en el nivel operativo C.10.")
    if legal_similarity.profile_count != suite.expected_similarity_profile_count:
        raise PrimaryCBRBenchmarkError("C.11 detectó cambio en los perfiles de similitud C.9.")
    if legal_similarity.total_pair_count != suite.expected_total_pair_count:
        raise PrimaryCBRBenchmarkError("C.11 detectó cambio en el universo de pares C.9.")
    if legal_similarity.eligible_pair_count != suite.expected_eligible_pair_count:
        raise PrimaryCBRBenchmarkError("C.11 detectó cambio en los pares elegibles C.9.")
    if level_registry.operational_cases:
        raise PrimaryCBRBenchmarkError("C.11 no admite CBRCase operativos en el dataset actual.")


def validate_primary_cbr_benchmark_suite(
    suite: PrimaryCBRBenchmarkSuite,
    classification: PrimaryCBRProblemInstitutionClassification,
    corpus_validation: PrimaryCBRCorpusValidationReport,
    family_registry: PrimaryCBRFamilyRegistry,
    legal_similarity: PrimaryCBRLegalSimilarityIndex,
    level_registry: PrimaryCBRLevelRegistry,
) -> None:
    _assert_global_contract(
        suite,
        classification,
        corpus_validation,
        family_registry,
        legal_similarity,
        level_registry,
    )

    known_ids = {item.situation_id for item in legal_similarity.profiles}
    covered_dimensions = {
        dimension
        for case in suite.cases
        for dimension in case.dimensions
    }
    if covered_dimensions != set(suite.required_dimensions):
        raise PrimaryCBRBenchmarkError("Los casos C.11 no cubren las seis dimensiones requeridas.")

    pair_decisions: set[PrimaryCBRLegalSimilarityDecision] = set()
    for case in suite.cases:
        if case.kind is PrimaryCBRBenchmarkCaseKind.SITUATION:
            if case.situation_id not in known_ids:
                raise PrimaryCBRBenchmarkError(
                    f"{case.case_id} referencia una situación fuera de C.9."
                )
        else:
            if case.left_situation_id not in known_ids or case.right_situation_id not in known_ids:
                raise PrimaryCBRBenchmarkError(
                    f"{case.case_id} referencia un par fuera de C.9."
                )
            if case.expected_similarity_decision is not None:
                pair_decisions.add(case.expected_similarity_decision)

    if pair_decisions != set(PrimaryCBRLegalSimilarityDecision):
        raise PrimaryCBRBenchmarkError(
            "C.11 debe ejercitar las cinco decisiones de similitud jurídica C.9."
        )


def _append_mismatch(
    diagnostics: list[str],
    label: str,
    observed: object,
    expected: object,
) -> None:
    if observed != expected:
        diagnostics.append(f"{label}: observado={observed!r}; esperado={expected!r}")


def _evaluate_situation_case(
    case: PrimaryCBRBenchmarkCase,
    classification: PrimaryCBRProblemInstitutionClassification,
    corpus_validation: PrimaryCBRCorpusValidationReport,
    family_registry: PrimaryCBRFamilyRegistry,
    level_registry: PrimaryCBRLevelRegistry,
) -> PrimaryCBRBenchmarkCaseResult:
    situation_id = case.situation_id
    if situation_id is None:
        raise PrimaryCBRBenchmarkError(f"{case.case_id} no contiene situation_id.")

    c5_by_id = {item.situation_id: item for item in classification.classifications}
    c7_by_id = {item.situation_id: item for item in corpus_validation.situations}
    c8_by_id = {item.situation_id: item for item in family_registry.assignments}
    c10_by_id = {item.situation_id: item for item in level_registry.assessments}
    c5 = c5_by_id[situation_id]
    c7 = c7_by_id[situation_id]
    c8 = c8_by_id[situation_id]
    c10 = c10_by_id[situation_id]

    diagnostics: list[str] = []
    if case.expected_problem_id is not None:
        _append_mismatch(
            diagnostics,
            "problem_id",
            c5.primary_problem_id,
            case.expected_problem_id,
        )
    if case.expect_institution_absent:
        _append_mismatch(
            diagnostics,
            "institution_id",
            c5.primary_institution_id,
            None,
        )
    elif case.expected_institution_id is not None:
        _append_mismatch(
            diagnostics,
            "institution_id",
            c5.primary_institution_id,
            case.expected_institution_id,
        )
    if case.expected_primary_family_id is not None:
        _append_mismatch(
            diagnostics,
            "primary_family_id",
            c8.primary_family_id,
            case.expected_primary_family_id,
        )
    missing_families = [
        family_id for family_id in case.required_family_ids if family_id not in c8.family_ids
    ]
    if missing_families:
        diagnostics.append("required_family_ids ausentes: " + ", ".join(missing_families))
    if case.expected_corpus_outcome is not None:
        _append_mismatch(
            diagnostics,
            "corpus_outcome",
            c7.validation_outcome,
            case.expected_corpus_outcome,
        )
    if case.expected_corpus_validated is not None:
        _append_mismatch(
            diagnostics,
            "corpus_validated",
            c7.corpus_validated,
            case.expected_corpus_validated,
        )
    if case.expected_highest_level is not None:
        _append_mismatch(
            diagnostics,
            "highest_level",
            c10.highest_level,
            case.expected_highest_level,
        )
    if case.expected_validated_level_eligible is not None:
        _append_mismatch(
            diagnostics,
            "validated_level_eligible",
            c10.validated_level_eligible,
            case.expected_validated_level_eligible,
        )
    if case.expected_operational_level_eligible is not None:
        _append_mismatch(
            diagnostics,
            "operational_level_eligible",
            c10.operational_level_eligible,
            case.expected_operational_level_eligible,
        )
    if case.expected_historical_regime_context is not None:
        historical_values = {
            c5.historical_regime_context,
            c7.historical_regime_context,
            c8.historical_regime_context,
            c10.historical_regime_context,
        }
        if historical_values != {case.expected_historical_regime_context}:
            diagnostics.append(
                "historical_regime_context no es coherente entre C.5/C.7/C.8/C.10."
            )

    return PrimaryCBRBenchmarkCaseResult(
        case_id=case.case_id,
        passed=not diagnostics,
        dimensions=case.dimensions,
        diagnostics=diagnostics,
    )


def _neighbor_rank(
    legal_similarity: PrimaryCBRLegalSimilarityIndex,
    left_situation_id: str,
    right_situation_id: str,
) -> int | None:
    group = next(
        item
        for item in legal_similarity.neighbors
        if item.situation_id == left_situation_id
    )
    match = next(
        (item for item in group.matches if item.situation_id == right_situation_id),
        None,
    )
    return None if match is None else match.rank


def _evaluate_pair_case(
    case: PrimaryCBRBenchmarkCase,
    legal_similarity: PrimaryCBRLegalSimilarityIndex,
) -> PrimaryCBRBenchmarkCaseResult:
    left_id = case.left_situation_id
    right_id = case.right_situation_id
    if left_id is None or right_id is None:
        raise PrimaryCBRBenchmarkError(f"{case.case_id} no contiene ambos IDs del par.")

    profiles = {item.situation_id: item for item in legal_similarity.profiles}
    decision, overall, _, _, _, _, conflicts = score_primary_cbr_legal_similarity(
        profiles[left_id],
        profiles[right_id],
    )
    observed_similarity = round(overall, 6)
    diagnostics: list[str] = []
    _append_mismatch(
        diagnostics,
        "similarity_decision",
        decision,
        case.expected_similarity_decision,
    )
    if case.expected_similarity is not None:
        _append_mismatch(
            diagnostics,
            "similarity",
            observed_similarity,
            round(case.expected_similarity, 6),
        )
    _append_mismatch(
        diagnostics,
        "critical_conflicts",
        conflicts,
        case.expected_conflict_fields,
    )
    if case.expected_left_neighbor_rank is not None:
        _append_mismatch(
            diagnostics,
            "left_neighbor_rank",
            _neighbor_rank(legal_similarity, left_id, right_id),
            case.expected_left_neighbor_rank,
        )

    return PrimaryCBRBenchmarkCaseResult(
        case_id=case.case_id,
        passed=not diagnostics,
        dimensions=case.dimensions,
        diagnostics=diagnostics,
        observed_similarity_decision=decision,
        observed_similarity=observed_similarity,
        observed_conflict_fields=list(conflicts),
    )


def run_primary_cbr_benchmark(
    suite: PrimaryCBRBenchmarkSuite,
    classification: PrimaryCBRProblemInstitutionClassification,
    corpus_validation: PrimaryCBRCorpusValidationReport,
    family_registry: PrimaryCBRFamilyRegistry,
    legal_similarity: PrimaryCBRLegalSimilarityIndex,
    level_registry: PrimaryCBRLevelRegistry,
) -> PrimaryCBRBenchmarkReport:
    validate_primary_cbr_benchmark_suite(
        suite,
        classification,
        corpus_validation,
        family_registry,
        legal_similarity,
        level_registry,
    )

    results: list[PrimaryCBRBenchmarkCaseResult] = []
    for case in suite.cases:
        if case.kind is PrimaryCBRBenchmarkCaseKind.SITUATION:
            result = _evaluate_situation_case(
                case,
                classification,
                corpus_validation,
                family_registry,
                level_registry,
            )
        else:
            result = _evaluate_pair_case(case, legal_similarity)
        results.append(result)

    covered = sorted(
        {dimension for result in results for dimension in result.dimensions},
        key=lambda item: item.value,
    )
    missing = sorted(
        set(suite.required_dimensions) - set(covered),
        key=lambda item: item.value,
    )
    passed_cases = sum(result.passed for result in results)
    pass_rate = passed_cases / len(results)
    global_contract_passed = not missing
    threshold_met = global_contract_passed and pass_rate >= suite.pass_threshold

    return PrimaryCBRBenchmarkReport(
        schema_version="1.0",
        benchmark_version=suite.benchmark_version,
        total_cases=len(results),
        passed_cases=passed_cases,
        pass_rate=round(pass_rate, 6),
        covered_dimensions=covered,
        missing_required_dimensions=missing,
        global_contract_passed=global_contract_passed,
        results=results,
        threshold_met=threshold_met,
        all_passed=threshold_met and passed_cases == len(results),
    )
