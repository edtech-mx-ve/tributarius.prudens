from __future__ import annotations

from typing import Protocol

from app.domain.cbr import CBRCase, CBRRetrievalResult, CBRReuseAssessment
from app.domain.documents import SourceType
from app.domain.isr import ISRTariff
from app.domain.jurisprudence import JurisprudenceRetrievalResult
from app.domain.normative import (
    NormativeApplicabilityRequest,
    NormativeApplicabilityResult,
)
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    HybridOrchestrationResult,
    OrchestrationStage,
    StageStatus,
    StageTrace,
)
from app.domain.query import QueryAnalysis, QueryIntent
from app.domain.rules import RuleEvaluationResult, RuleSet
from app.services.cbr_reasoning import assess_case_reuse
from app.services.normative_engine import evaluate_normative_applicability
from app.services.rule_engine import evaluate_rules
from calculators.isr import ISRCalculationError, calculate_isr
from cbr.engine import retrieve_similar_cases
from jurisprudence.activation import decide_jurisprudence_activation
from jurisprudence.retrieval import JurisprudenceRetrievalError, JurisprudenceRetriever
from llm.errors import LLMError
from llm.models import DeterministicEvidence
from llm.service import LlamaRAGService
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalResult


class QueryAnalyzerLike(Protocol):
    def analyze(self, query: str) -> QueryAnalysis:
        ...


class RetrieverLike(Protocol):
    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        ...


def _safe_fact_value(name: str, value: str) -> object:
    clean = value.strip()
    if name == "fiscal_year" and clean.isdigit():
        return int(clean)
    return clean


def build_fact_map(analysis: QueryAnalysis) -> dict[str, object]:
    """Convierte hechos del analizador sin inferir datos ausentes."""
    result: dict[str, object] = {}
    for fact in analysis.facts:
        key = fact.name.strip().lower()
        result[key] = _safe_fact_value(key, fact.value)
    return result


def _retrieval_filters(analysis: QueryAnalysis) -> RetrievalFilters:
    del analysis
    return RetrievalFilters(
        source_types={
            SourceType.PRODECON,
            SourceType.UNAM,
            SourceType.NORMATIVA,
        }
    )


def _query_matter(analysis: QueryAnalysis) -> str | None:
    for fact in analysis.facts:
        if fact.name.strip().casefold() == "matter":
            return fact.value.strip()
    return None


def _evaluate_normative_candidates(
    request: HybridOrchestrationRequest,
) -> tuple[list[NormativeApplicabilityResult], list[str]]:
    results: list[NormativeApplicabilityResult] = []
    refs: list[str] = []
    for candidate in request.normative_candidates:
        result = evaluate_normative_applicability(
            NormativeApplicabilityRequest(
                legal_unit_id=candidate.legal_unit_id,
                version_label=candidate.version_label,
                effective_from=candidate.effective_from,
                effective_to=candidate.effective_to,
                fiscal_year=candidate.fiscal_year,
                query_date=request.query_date,
                query_fiscal_year=request.query_fiscal_year,
            )
        )
        results.append(result)
        if result.applicable:
            refs.append(candidate.ref)
    return results, refs


def _deterministic_evidence(
    normative_refs: list[str],
    rule_result: RuleEvaluationResult,
    isr_result: object | None,
    cbr_result: CBRRetrievalResult | None,
    jurisprudence_result: JurisprudenceRetrievalResult | None,
) -> DeterministicEvidence:
    calculations: list[str] = []
    if isr_result is not None:
        final_tax = getattr(isr_result, "final_tax", None)
        taxable_base = getattr(isr_result, "taxable_base", None)
        calculations.append(
            f"ISR: taxable_base={taxable_base}; final_tax={final_tax}"
        )

    similar_cases: list[str] = []
    if cbr_result is not None:
        similar_cases = [
            (
                f"{item.case_id}: similarity={item.similarity:.3f}; "
                f"status={item.status.value}; {item.resolution_summary}"
            )
            for item in cbr_result.matches
        ]

    jurisprudential_criteria: list[str] = []
    if jurisprudence_result is not None:
        jurisprudential_criteria = [
            (
                f"{hit.metadata.identifier}: relation={hit.metadata.relation_type.value}; "
                f"status={hit.metadata.status.value}; source={hit.metadata.source_reference}"
            )
            for hit in jurisprudence_result.hits
        ]

    return DeterministicEvidence(
        applicable_normative_refs=normative_refs,
        rule_conclusions=[
            f"{item.rule_id}@{item.version}: {item.conclusion}"
            for item in rule_result.matched_rules
        ],
        calculations=calculations,
        similar_cases=similar_cases,
        jurisprudential_criteria=jurisprudential_criteria,
        requires_human_review=(
            rule_result.requires_human_review
            or (
                any(item.requires_human_review for item in cbr_result.matches)
                if cbr_result is not None
                else False
            )
            or (
                jurisprudence_result.requires_human_review
                if jurisprudence_result is not None
                else False
            )
        ),
    )


class HybridOrchestrator:
    """Coordina análisis, RAG, normativa, reglas, cálculo, CBR y explicación."""

    def __init__(
        self,
        *,
        query_analyzer: QueryAnalyzerLike,
        retriever: RetrieverLike,
        llm_service: LlamaRAGService,
        rule_set: RuleSet,
        isr_tariff: ISRTariff | None = None,
        cbr_cases: list[CBRCase] | None = None,
        jurisprudence_retriever: JurisprudenceRetriever | None = None,
    ) -> None:
        self._query_analyzer = query_analyzer
        self._retriever = retriever
        self._llm_service = llm_service
        self._rule_set = rule_set
        self._isr_tariff = isr_tariff
        self._cbr_cases = list(cbr_cases or [])
        self._jurisprudence_retriever = jurisprudence_retriever

    def run(self, request: HybridOrchestrationRequest) -> HybridOrchestrationResult:
        traces: list[StageTrace] = []

        analysis = self._query_analyzer.analyze(request.query)
        traces.append(
            StageTrace(
                stage=OrchestrationStage.QUERY_ANALYSIS,
                status=StageStatus.COMPLETED,
                detail=f"Intento principal: {analysis.primary_intent.value}.",
            )
        )

        retrieval = self._retriever.search(
            analysis.normalized_query,
            top_k=request.top_k,
            filters=_retrieval_filters(analysis),
        )
        traces.append(
            StageTrace(
                stage=OrchestrationStage.RETRIEVAL,
                status=StageStatus.COMPLETED,
                detail=f"Chunks recuperados: {retrieval.returned_count}.",
            )
        )

        normative_results, applicable_refs = _evaluate_normative_candidates(request)
        traces.append(
            StageTrace(
                stage=OrchestrationStage.NORMATIVE,
                status=StageStatus.COMPLETED,
                detail=f"Referencias normativas aplicables: {len(applicable_refs)}.",
            )
        )

        jurisprudence_activation = decide_jurisprudence_activation(
            analysis,
            has_applicable_norms=bool(applicable_refs),
        )
        jurisprudence_result = None
        jurisprudence_review = jurisprudence_activation.requires_human_review
        if not jurisprudence_activation.activated:
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.JURISPRUDENCE,
                    status=StageStatus.SKIPPED,
                    detail=jurisprudence_activation.detail,
                )
            )
        elif self._jurisprudence_retriever is None:
            jurisprudence_review = True
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.JURISPRUDENCE,
                    status=StageStatus.DEGRADED,
                    detail=(
                        "Jurisprudencia requerida, pero el retriever jurisprudencial "
                        "no está configurado."
                    ),
                )
            )
        else:
            try:
                jurisprudence_result = self._jurisprudence_retriever.search(
                    analysis.normalized_query,
                    activation=jurisprudence_activation,
                    query_date=request.query_date,
                    applicable_normative_refs=set(applicable_refs),
                    top_k=request.top_k,
                    matter=_query_matter(analysis),
                )
            except JurisprudenceRetrievalError:
                jurisprudence_review = True
                traces.append(
                    StageTrace(
                        stage=OrchestrationStage.JURISPRUDENCE,
                        status=StageStatus.DEGRADED,
                        detail=(
                            "La recuperación jurisprudencial falló de forma controlada; "
                            "se preservó el análisis normativo."
                        ),
                    )
                )
            else:
                jurisprudence_review = (
                    jurisprudence_review
                    or jurisprudence_result.requires_human_review
                )
                traces.append(
                    StageTrace(
                        stage=OrchestrationStage.JURISPRUDENCE,
                        status=StageStatus.COMPLETED,
                        detail=(
                            "Criterios jurisprudenciales elegibles: "
                            f"{jurisprudence_result.returned_count}."
                        ),
                    )
                )

        fact_map = build_fact_map(analysis)
        rule_result = evaluate_rules(
            self._rule_set,
            fact_map,
            set(applicable_refs),
        )
        traces.append(
            StageTrace(
                stage=OrchestrationStage.RULES,
                status=StageStatus.COMPLETED,
                detail=f"Reglas activadas: {len(rule_result.matched_rules)}.",
            )
        )

        isr_result = None
        isr_review = False
        if analysis.primary_intent == QueryIntent.CALCULATE_ISR:
            if analysis.requires_clarification:
                isr_review = True
                traces.append(
                    StageTrace(
                        stage=OrchestrationStage.ISR,
                        status=StageStatus.SKIPPED,
                        detail="Cálculo omitido: faltan datos requeridos.",
                    )
                )
            elif request.isr_input is None or self._isr_tariff is None:
                isr_review = True
                traces.append(
                    StageTrace(
                        stage=OrchestrationStage.ISR,
                        status=StageStatus.SKIPPED,
                        detail="Cálculo omitido: entrada o tarifa ISR no disponible.",
                    )
                )
            elif request.isr_input.normative_ref not in applicable_refs:
                isr_review = True
                traces.append(
                    StageTrace(
                        stage=OrchestrationStage.ISR,
                        status=StageStatus.SKIPPED,
                        detail="Cálculo omitido: referencia normativa no validada.",
                    )
                )
            else:
                try:
                    isr_result = calculate_isr(request.isr_input, self._isr_tariff)
                except ISRCalculationError:
                    isr_review = True
                    traces.append(
                        StageTrace(
                            stage=OrchestrationStage.ISR,
                            status=StageStatus.DEGRADED,
                            detail="El cálculo ISR fue rechazado por validación determinista.",
                        )
                    )
                else:
                    traces.append(
                        StageTrace(
                            stage=OrchestrationStage.ISR,
                            status=StageStatus.COMPLETED,
                            detail="Cálculo ISR ejecutado de forma determinista.",
                        )
                    )
        else:
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.ISR,
                    status=StageStatus.SKIPPED,
                    detail="La intención principal no requiere cálculo ISR.",
                )
            )

        cbr_result = None
        cbr_assessments: list[CBRReuseAssessment] = []
        cbr_review = False
        if request.cbr_query is None:
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.CBR,
                    status=StageStatus.SKIPPED,
                    detail="No se solicitó recuperación de casos semejantes.",
                )
            )
        elif not self._cbr_cases:
            cbr_review = True
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.CBR,
                    status=StageStatus.DEGRADED,
                    detail="CBR solicitado, pero no hay corpus de casos disponible.",
                )
            )
        else:
            cbr_result = retrieve_similar_cases(request.cbr_query, self._cbr_cases)
            cbr_assessments = [
                assess_case_reuse(
                    item,
                    current_normative_refs=set(applicable_refs),
                )
                for item in cbr_result.matches
            ]
            cbr_review = any(
                item.requires_human_review for item in cbr_assessments
            )
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.CBR,
                    status=StageStatus.COMPLETED,
                    detail=f"Casos semejantes recuperados: {cbr_result.returned_count}.",
                )
            )

        deterministic = _deterministic_evidence(
            applicable_refs,
            rule_result,
            isr_result,
            cbr_result,
            jurisprudence_result,
        )
        explanation = None
        llm_review = False
        try:
            explanation = self._llm_service.explain(
                retrieval,
                deterministic_evidence=deterministic,
            )
        except LLMError:
            llm_review = True
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.EXPLANATION,
                    status=StageStatus.DEGRADED,
                    detail="Llama no estuvo disponible; se preservó el resultado determinista.",
                )
            )
        else:
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.EXPLANATION,
                    status=StageStatus.COMPLETED,
                    detail=(
                        "Explicación generada con evidencia recuperada "
                        "y resultados deterministas."
                    ),
                )
            )

        normative_review = any(
            result.requires_human_review for result in normative_results
        )
        explanation_review = (
            explanation.answer.requires_human_review if explanation is not None else False
        )

        return HybridOrchestrationResult(
            analysis=analysis,
            retrieval=retrieval,
            normative_results=normative_results,
            applicable_normative_refs=applicable_refs,
            jurisprudence_result=jurisprudence_result,
            rule_result=rule_result,
            isr_result=isr_result,
            cbr_result=cbr_result,
            cbr_reuse_assessments=cbr_assessments,
            explanation=explanation,
            traces=traces,
            requires_human_review=any(
                (
                    analysis.requires_human_review,
                    normative_review,
                    rule_result.requires_human_review,
                    isr_review,
                    cbr_review,
                    jurisprudence_review,
                    llm_review,
                    explanation_review,
                )
            ),
        )
