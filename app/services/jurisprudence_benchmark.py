from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import ValidationError

from app.domain.jurisprudence import (
    JurisprudenceCriterionType,
    JurisprudenceStatus,
    NormRelationType,
)
from app.domain.jurisprudence_benchmark import (
    JurisprudenceBenchmarkCase,
    JurisprudenceBenchmarkCaseResult,
    JurisprudenceBenchmarkReport,
    JurisprudenceBenchmarkScenario,
    JurisprudenceBenchmarkSuite,
)
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.domain.jurisprudence_normative_relations import (
    JurisprudenceNormativeLinkBasis,
    JurisprudenceNormativeMention,
    JurisprudenceNormativeRelationRecord,
    JurisprudenceNormativeUnitType,
)
from app.domain.jurisprudence_ratio import (
    JurisprudenceRatioRecord,
    JurisprudenceRatioSourceSection,
)
from app.domain.jurisprudence_temporal import (
    JurisprudencePublicationDatePrecision,
    JurisprudenceTemporalRecord,
)
from app.services.jurisprudence_decision_application import (
    evaluate_jurisprudence_for_legal_decision,
)
from app.services.jurisprudence_hybrid_stage import run_session_jurisprudence_stage
from llm.providers.runtime_query import RuntimeQueryAnalyzerProvider
from llm.query_analyzer import QueryAnalyzer


class JurisprudenceBenchmarkError(RuntimeError):
    pass


def _default_suite_path() -> Path:
    return Path(__file__).resolve().parents[1] / "resources" / "jurisprudence_benchmark_suite.json"


def load_jurisprudence_benchmark_suite(
    path: Path | None = None,
) -> JurisprudenceBenchmarkSuite:
    source = path or _default_suite_path()
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        return JurisprudenceBenchmarkSuite.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise JurisprudenceBenchmarkError("El benchmark E.7 no es válido.") from exc


def validate_jurisprudence_benchmark_suite(suite: JurisprudenceBenchmarkSuite) -> None:
    JurisprudenceBenchmarkSuite.model_validate(suite.model_dump(mode="json"))


def _document_id(case: JurisprudenceBenchmarkCase) -> str:
    return case.case_id.casefold().replace("-", "_")


def _sha(case: JurisprudenceBenchmarkCase) -> str:
    suffix = int(case.case_id.rsplit("-", 1)[1])
    return f"{suffix:x}"[-1] * 64


def _relation_ref(case: JurisprudenceBenchmarkCase) -> tuple[str, str, str]:
    if case.scenario is JurisprudenceBenchmarkScenario.UNRELATED_NORM:
        return "cff", "22", "cff:articulo_22"
    return "lisr", "113-E", "lisr:articulo_113_e"


def _material_relation(case: JurisprudenceBenchmarkCase) -> bool:
    return case.scenario is not JurisprudenceBenchmarkScenario.CITATION_ONLY


def _relation_type(case: JurisprudenceBenchmarkCase) -> NormRelationType:
    if case.scenario is JurisprudenceBenchmarkScenario.CITATION_ONLY:
        return NormRelationType.CITES
    return NormRelationType.INTERPRETS


def _thesis_text(case: JurisprudenceBenchmarkCase) -> tuple[str, str, str]:
    if case.scenario is JurisprudenceBenchmarkScenario.UNRELATED_NORM:
        facts = (
            "Una persona física en RESICO para ISR planteó una controversia fiscal "
            "relacionada con devolución y el artículo 22 del CFF."
        )
        criterion = "El artículo 22 del CFF regula el supuesto de devolución examinado."
        justification = (
            "La Justificación interpreta el artículo 22 del CFF para resolver la "
            "controversia sobre devolución, sin interpretar el artículo 113-E de la LISR."
        )
        return facts, criterion, justification

    facts = (
        "Una persona física en RESICO para ISR superó el límite de ingresos durante "
        "el ejercicio fiscal y controvirtió las consecuencias del artículo 113-E de la LISR."
    )
    criterion = (
        "El artículo 113-E de la LISR debe interpretarse atendiendo a la condición "
        "económica del RESICO y al ejercicio fiscal."
    )
    justification = (
        "La Justificación interpreta el artículo 113-E de la LISR: cuando una persona "
        "física en RESICO para ISR supera el límite de ingresos durante el ejercicio, "
        "deja de reunir la característica económica necesaria para permanecer en el régimen."
    )
    if case.scenario is JurisprudenceBenchmarkScenario.CITATION_ONLY:
        criterion = "La tesis menciona el artículo 113-E de la LISR como referencia normativa."
        justification = (
            "La Justificación describe el contexto RESICO e ISR y cita el artículo 113-E "
            "de la LISR sin formular una relación interpretativa explícita."
        )
    if case.scenario is JurisprudenceBenchmarkScenario.REFERENCE_2032043:
        facts = (
            "Una persona física en RESICO para ISR superó el límite de ingresos y discutió "
            "si la regla 3.13.33 de la RMF 2023 contradecía el artículo 113-E de la LISR."
        )
        criterion = (
            "La regla 3.13.33 de la RMF 2023 no viola la subordinación jerárquica frente "
            "al artículo 113-E de la LISR."
        )
        justification = (
            "La Justificación interpreta el artículo 113-E de la LISR en el sentido de "
            "que superar el límite económico durante el ejercicio hace perder la "
            "característica económica del RESICO y produce el cambio de régimen correspondiente."
        )
    return facts, criterion, justification


def _build_fixture(
    case: JurisprudenceBenchmarkCase,
) -> tuple[
    JurisprudenceDocumentRepresentation,
    JurisprudenceExtractedMetadata,
    JurisprudenceNormativeRelationRecord,
    JurisprudenceTemporalRecord,
    JurisprudenceRatioRecord,
]:
    document_id = _document_id(case)
    sha = _sha(case)
    corpus_id, unit, normative_ref = _relation_ref(case)
    facts, criterion, justification = _thesis_text(case)
    missing_justification = (
        case.scenario is JurisprudenceBenchmarkScenario.MISSING_JUSTIFICATION
    )

    page_text = " ".join(
        [
            case.query,
            f"Hechos: {facts}",
            f"Criterio jurídico: {criterion}",
            "Justificación: " + (justification if not missing_justification else "No disponible."),
        ]
    )
    document = JurisprudenceDocumentRepresentation(
        document_id=document_id,
        original_filename=f"{case.case_id.casefold()}.pdf",
        source_sha256=sha,
        page_count=1,
        extracted_characters=len(page_text),
        pages=[JurisprudencePage(number=1, text=page_text, has_extractable_text=True)],
        full_text=page_text,
    )

    metadata = JurisprudenceExtractedMetadata(
        identifier="2032043" if case.reference_thesis_2032043 else case.case_id,
        thesis_number="P./J. 58/2026 (12a.)" if case.reference_thesis_2032043 else None,
        title=(
            "RESICO. INTERPRETACIÓN DEL ARTÍCULO 113-E DE LA LISR."
            if corpus_id == "lisr"
            else "DEVOLUCIÓN. INTERPRETACIÓN DEL ARTÍCULO 22 DEL CFF."
        ),
        court_or_body="Pleno" if case.reference_thesis_2032043 else "Órgano benchmark E.7",
        criterion_type=JurisprudenceCriterionType.JURISPRUDENCE,
        publication_date_text="17 de abril de 2026",
        status=JurisprudenceStatus.CURRENT,
        matter="Constitucional" if case.reference_thesis_2032043 else "ISR",
        binding_effective_date_text="20 de abril de 2026",
        facts_text=facts,
        legal_criterion_text=criterion,
        justification_text=None if missing_justification else justification,
        related_normative_refs=[normative_ref],
        relation_type=_relation_type(case),
        source_pages=[1],
        requires_human_review=True,
    )

    material = _material_relation(case)
    mention = JurisprudenceNormativeMention(
        mention_id="E3-NORM-001",
        source_page=1,
        source_excerpt=(
            f"La Justificación interpreta el artículo {unit} de {corpus_id.upper()}."
            if material
            else f"La tesis menciona el artículo {unit} de {corpus_id.upper()}."
        ),
        legal_unit_type=JurisprudenceNormativeUnitType.ARTICLE,
        legal_unit=unit,
        instrument_match=corpus_id.upper(),
        candidate_corpus_id=corpus_id,
        candidate_normative_ref=normative_ref,
        corpus_in_primary_manifest=True,
        relation_type=_relation_type(case),
        linkage_basis=(
            JurisprudenceNormativeLinkBasis.EXPLICIT_RELATION_LANGUAGE
            if material
            else JurisprudenceNormativeLinkBasis.EXPLICIT_NORMATIVE_MENTION
        ),
        material_relation_explicit=material,
    )
    relation = JurisprudenceNormativeRelationRecord(
        document_id=document_id,
        source_sha256=sha,
        normative_corpus_ids=[corpus_id],
        mentions=[mention],
        mention_count=1,
        linked_to_primary_corpus_count=1,
        unresolved_or_external_count=0,
        explicit_material_relation_count=1 if material else 0,
    )

    publication = date(2026, 4, 17)
    binding = date(2026, 4, 20)
    if case.scenario not in {
        JurisprudenceBenchmarkScenario.NOT_YET_MANDATORY,
        JurisprudenceBenchmarkScenario.REFERENCE_2032043,
    }:
        publication = date(2026, 1, 15)
        binding = date(2026, 1, 19)
    temporal = JurisprudenceTemporalRecord(
        document_id=document_id,
        source_sha256=sha,
        criterion_type=JurisprudenceCriterionType.JURISPRUDENCE,
        publication_date_text=publication.isoformat(),
        parsed_publication_start=publication,
        parsed_publication_end=publication,
        publication_date_precision=JurisprudencePublicationDatePrecision.DAY,
        publication_date_source_pages=[1],
        binding_character_mandatory=True,
        binding_character_basis="official_type_jurisprudence",
        binding_effective_date_text=binding.isoformat(),
        parsed_binding_start=binding,
        parsed_binding_end=binding,
        binding_date_precision=JurisprudencePublicationDatePrecision.DAY,
        binding_date_source_pages=[1],
        criterion_status_claim=JurisprudenceStatus.CURRENT,
        binding_force_evaluated=True,
    )

    ratio = JurisprudenceRatioRecord(
        document_id=document_id,
        source_sha256=sha,
        criterion_type=JurisprudenceCriterionType.JURISPRUDENCE,
        facts_text=facts,
        legal_criterion_text=criterion,
        justification_text=None if missing_justification else justification,
        facts_source_pages=[1],
        legal_criterion_source_pages=[1],
        justification_source_pages=[] if missing_justification else [1],
        ratio_source_section=(
            JurisprudenceRatioSourceSection.UNKNOWN
            if missing_justification
            else JurisprudenceRatioSourceSection.JUSTIFICATION
        ),
        ratio_source_text=None if missing_justification else justification,
        structured_thesis_sections_established=not missing_justification,
        ratio_source_established=not missing_justification,
    )
    return document, metadata, relation, temporal, ratio


def _matter_from_analysis(case: JurisprudenceBenchmarkCase) -> str | None:
    analysis = QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(case.query)
    for fact in analysis.facts:
        if fact.name.strip().casefold() == "matter":
            return fact.value
    return None


def _append_mismatch(
    diagnostics: list[str],
    label: str,
    expected: object,
    observed: object,
) -> None:
    if expected != observed:
        diagnostics.append(f"{label}: esperado={expected!r}; observado={observed!r}")


def _evaluate_case(case: JurisprudenceBenchmarkCase) -> JurisprudenceBenchmarkCaseResult:
    diagnostics: list[str] = []
    if case.scenario is JurisprudenceBenchmarkScenario.WITHOUT_JURISPRUDENCE:
        return JurisprudenceBenchmarkCaseResult(
            case_id=case.case_id,
            scenario=case.scenario,
            passed=True,
            diagnostics=[],
            retrieved_count=0,
            authorized_evidence_count=0,
            evidence_decisions=[],
            application_statuses=[],
            decision_effects=[],
            binding_jurisprudence_applies=False,
            requires_human_review=False,
            session_scope_preserved=True,
            justification_ratio_boundary_preserved=True,
            normative_basis_preserved=True,
            single_conclusion_preserved=True,
            reference_thesis_2032043=False,
        )

    analysis = QueryAnalyzer(RuntimeQueryAnalyzerProvider()).analyze(case.query)
    document, metadata, relation, temporal, ratio = _build_fixture(case)
    query_date = date.fromisoformat(case.query_date)
    session = run_session_jurisprudence_stage(
        query=analysis.normalized_query,
        documents=[document],
        metadata_by_document_id={document.document_id: metadata},
        applicable_normative_refs=set(case.applicable_normative_refs),
        matter=_matter_from_analysis(case),
        top_k=5,
        normative_relation_records={document.document_id: relation},
        temporal_records={document.document_id: temporal},
        ratio_records={document.document_id: ratio},
        query_date=query_date,
    )
    application = evaluate_jurisprudence_for_legal_decision(
        analysis=analysis,
        session_result=session,
        ratio_records={document.document_id: ratio},
        normative_relation_records={document.document_id: relation},
    )

    integration = session.evidence_integration
    if integration is None:
        raise JurisprudenceBenchmarkError("E.7 esperaba integración E.5 disponible.")

    evidence_decisions = [item.decision for item in integration.assessments]
    application_statuses = [item.status for item in application.assessments]
    decision_effects = [item.decision_effect for item in application.assessments]
    binding_applies = bool(application.applicable_document_ids)
    observed_review = (
        application.requires_human_review
        if application.assessments
        else session.requires_human_review
    )
    session_scope_preserved = (
        integration.source_scope == "session"
        and all(item.source_scope == "session" for item in integration.assessments)
        and all(item.source_scope == "session" for item in application.assessments)
    )
    ratio_boundary = (
        all(
            not item.authorized_for_evidence
            or (
                item.ratio_source_established
                and item.ratio_page_contains_justification
            )
            for item in integration.assessments
        )
        and all(item.ratio_source_is_justification for item in application.assessments)
    )
    normative_basis_preserved = (
        integration.normative_evidence_preserved
        and all(item.normative_basis_preserved for item in application.assessments)
        and application.normative_basis_preserved
    )
    single_conclusion_preserved = (
        application.single_conclusion_preserved
        and all(not item.can_create_second_conclusion for item in application.assessments)
    )

    _append_mismatch(
        diagnostics,
        "retrieved_count",
        case.expected_retrieved_count,
        session.retrieval.returned_count,
    )
    _append_mismatch(
        diagnostics,
        "authorized_evidence_count",
        case.expected_authorized_evidence_count,
        integration.admitted_count,
    )
    _append_mismatch(
        diagnostics,
        "evidence_decisions",
        case.expected_evidence_decisions,
        evidence_decisions,
    )
    _append_mismatch(
        diagnostics,
        "application_statuses",
        case.expected_application_statuses,
        application_statuses,
    )
    _append_mismatch(
        diagnostics,
        "decision_effects",
        case.expected_decision_effects,
        decision_effects,
    )
    _append_mismatch(
        diagnostics,
        "binding_jurisprudence_applies",
        case.expected_binding_jurisprudence_applies,
        binding_applies,
    )
    _append_mismatch(
        diagnostics,
        "requires_human_review",
        case.expected_requires_human_review,
        observed_review,
    )
    if not session_scope_preserved:
        diagnostics.append("session_scope_not_preserved")
    if not ratio_boundary:
        diagnostics.append("ratio_justification_boundary_not_preserved")
    if not normative_basis_preserved:
        diagnostics.append("normative_basis_not_preserved")
    if not single_conclusion_preserved:
        diagnostics.append("single_conclusion_not_preserved")

    return JurisprudenceBenchmarkCaseResult(
        case_id=case.case_id,
        scenario=case.scenario,
        passed=not diagnostics,
        diagnostics=diagnostics,
        retrieved_count=session.retrieval.returned_count,
        authorized_evidence_count=integration.admitted_count,
        evidence_decisions=evidence_decisions,
        application_statuses=application_statuses,
        decision_effects=decision_effects,
        binding_jurisprudence_applies=binding_applies,
        requires_human_review=observed_review,
        session_scope_preserved=session_scope_preserved,
        justification_ratio_boundary_preserved=ratio_boundary,
        normative_basis_preserved=normative_basis_preserved,
        single_conclusion_preserved=single_conclusion_preserved,
        reference_thesis_2032043=case.reference_thesis_2032043,
    )


def run_jurisprudence_benchmark(
    suite: JurisprudenceBenchmarkSuite | None = None,
) -> JurisprudenceBenchmarkReport:
    benchmark = suite or load_jurisprudence_benchmark_suite()
    validate_jurisprudence_benchmark_suite(benchmark)
    results = [_evaluate_case(case) for case in benchmark.cases]
    total = len(results)
    passed = sum(result.passed for result in results)
    pass_rate = passed / total if total else 0.0
    without = next(
        item
        for item in results
        if item.scenario is JurisprudenceBenchmarkScenario.WITHOUT_JURISPRUDENCE
    )
    reference = next(item for item in results if item.reference_thesis_2032043)

    return JurisprudenceBenchmarkReport(
        schema_version=benchmark.schema_version,
        benchmark_version=benchmark.benchmark_version,
        total_cases=total,
        passed_cases=passed,
        pass_rate=pass_rate,
        pass_threshold=benchmark.pass_threshold,
        threshold_met=pass_rate >= benchmark.pass_threshold,
        all_passed=passed == total,
        results=results,
        without_jurisprudence_case_passed=without.passed,
        reference_thesis_2032043_passed=reference.passed,
        optionality_contract_passed=(
            without.passed
            and without.retrieved_count == 0
            and not without.binding_jurisprudence_applies
        ),
        session_scope_contract_passed=all(
            item.session_scope_preserved for item in results
        ),
        ratio_justification_contract_passed=all(
            item.justification_ratio_boundary_preserved for item in results
        ),
        normative_basis_contract_passed=all(
            item.normative_basis_preserved for item in results
        ),
        single_conclusion_contract_passed=all(
            item.single_conclusion_preserved for item in results
        ),
        validates_current_dataset_only=benchmark.validates_current_dataset_only,
        claims_full_mexican_jurisprudence_coverage=(
            benchmark.claims_full_mexican_jurisprudence_coverage
        ),
    )
