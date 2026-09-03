from __future__ import annotations

from typing import Protocol

from app.domain.cbr import CBRCase, CBRRetrievalResult, CBRReuseAssessment
from app.domain.documents import SourceType
from app.domain.isr import ISRTariff
from app.domain.jurisprudence import JurisprudenceRetrievalResult
from app.domain.legal_heuristics import LegalHeuristicEvaluation
from app.domain.normative import (
    NormativeApplicabilityRequest,
    NormativeApplicabilityResult,
)
from app.domain.orchestration import (
    HybridOrchestrationRequest,
    HybridOrchestrationResult,
    NormativeCandidate,
    OrchestrationStage,
    StageStatus,
    StageTrace,
)
from app.domain.query import (
    ExtractedFact,
    FactOrigin,
    QueryAnalysis,
    QueryIntent,
)
from app.domain.rules import RuleEvaluationResult, RuleSet
from app.services.cbr_reasoning import assess_case_reuse
from app.services.focused_normative_rag import execute_focused_rag
from app.services.full_corpus_expansion import execute_full_corpus_expansion
from app.services.hybrid_isr_stage import run_isr_stage
from app.services.hybrid_reasoning_coordinator import coordinate_rbs_cbr
from app.services.hybrid_reasoning_normalization import (
    normalize_cbr_result,
    normalize_rbs_result,
)
from app.services.isr_traceability import (
    ISRTraceabilityError,
    build_isr_calculation_trace,
    verify_isr_calculation_trace,
)
from app.services.legal_heuristic_explanation import (
    build_heuristic_explanation_evidence,
)
from app.services.legal_heuristics_stage import run_legal_heuristics_stage
from app.services.legal_hypothesis_stage import (
    LegalHypothesisGeneratorLike,
    run_legal_hypothesis_stage,
)
from app.services.legal_hypothesis_verification_stage import (
    run_legal_hypothesis_verification_stage,
)
from app.services.llm_traceability import build_llm_trace
from app.services.normative_engine import evaluate_normative_applicability
from app.services.normative_rag_bridge import (
    build_normative_candidates,
    build_rule_normative_refs,
)
from app.services.normative_temporal_runtime_guard import TemporalRuntimeGuard
from app.services.query_fact_compat_19s_r15 import query_fact_value
from app.services.rule_engine import evaluate_rules
from app.services.temporal_control import (
    execute_temporal_control,
    resolve_temporal_query_context,
)
from calculators.isr_tariff_registry import ISRTariffRegistry
from cbr.engine import retrieve_similar_cases
from jurisprudence.activation import decide_jurisprudence_activation
from jurisprudence.retrieval import JurisprudenceRetrievalError, JurisprudenceRetriever
from llm.errors import LLMError
from llm.models import DeterministicEvidence
from llm.service import LlamaRAGService
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalResult


class QueryAnalyzerLike(Protocol):
    def analyze(self, query: str) -> QueryAnalysis: ...


class RetrieverLike(Protocol):
    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult: ...


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


_MATERIAL_STOPWORDS = frozenset(
    {
        "a",
        "al",
        "ante",
        "como",
        "con",
        "de",
        "del",
        "el",
        "en",
        "es",
        "fiscal",
        "fiscales",
        "impuesto",
        "impuestos",
        "la",
        "las",
        "lo",
        "los",
        "mexico",
        "para",
        "persona",
        "por",
        "que",
        "se",
        "sin",
        "su",
        "sus",
        "tasa",
        "una",
        "un",
        "y",
        "iva",
        "isr",
        "2026",
        "pagar",
        "aplicar",
        "regla",
        "norma",
    }
)


def _fold_tokens(text: str) -> set[str]:
    import re
    import unicodedata

    folded = unicodedata.normalize("NFKD", text.casefold())
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    return {
        token
        for token in re.findall(r"[a-z0-9][a-z0-9_-]{2,}", ascii_text)
        if token not in _MATERIAL_STOPWORDS
    }


def _merge_request_context(
    analysis: QueryAnalysis,
    request: HybridOrchestrationRequest,
) -> QueryAnalysis:
    """Propaga contexto estructurado sin inferir hechos no proporcionados."""
    facts = list(analysis.facts)
    missing = list(analysis.missing_fields)
    if request.query_fiscal_year is not None:
        names = {item.name.strip().casefold() for item in facts}
        if "fiscal_year" not in names:
            facts.append(
                ExtractedFact(
                    name="fiscal_year",
                    value=str(request.query_fiscal_year),
                    origin=FactOrigin.EXPLICIT,
                )
            )
        missing = [item for item in missing if item.name.strip().casefold() != "fiscal_year"]
    return analysis.model_copy(
        update={
            "facts": facts,
            "missing_fields": missing,
            "requires_clarification": (
                analysis.requires_clarification or bool(missing) or bool(analysis.ambiguities)
            ),
        }
    )


def _materially_relevant_hit(
    analysis: QueryAnalysis,
    hit: object,
) -> bool:
    """Gate conservador de pertinencia antes de promoción normativa.

    La temporalidad se evalúa después. Este gate impide que una disposición
    temporalmente conocida se convierta en aplicable solo por compartir
    vocabulario fiscal genérico.
    """
    metadata = getattr(hit, "metadata", None)
    text = getattr(hit, "text", "")
    if metadata is None:
        return False

    document_id = str(getattr(metadata, "document_id", "")).casefold()
    matter = (_query_matter(analysis) or "").casefold()

    if analysis.primary_intent == QueryIntent.KNOW_RIGHTS:
        return document_id in {"lfdc", "cff"}

    if analysis.primary_intent == QueryIntent.CALCULATE_ISR or matter == "isr":
        allowed = {"lisr", "reg_lisr_060516", "rmf_2026"}
        if document_id not in allowed:
            return False

    if analysis.primary_intent == QueryIntent.CALCULATE_IVA or matter == "iva":
        allowed = {"liva", "reg_liva_250914", "rmf_2026"}
        if document_id not in allowed:
            return False

    # La RMF contiene miles de supuestos especiales. Para una consulta genérica
    # exige contexto material específico compartido, no solo IVA/ISR/año/tasa.
    if document_id == "rmf_2026":
        query_tokens = _fold_tokens(analysis.normalized_query)
        hit_tokens = _fold_tokens(str(text))
        if len(query_tokens & hit_tokens) < 2:
            return False

    return True


def _filter_material_candidates(
    analysis: QueryAnalysis,
    retrieval: RetrievalResult,
    candidates: list[NormativeCandidate],
) -> list[NormativeCandidate]:
    relevant_refs = {
        hit.chunk_id for hit in retrieval.hits if _materially_relevant_hit(analysis, hit)
    }
    return [
        candidate for candidate in candidates if getattr(candidate, "ref", None) in relevant_refs
    ]


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
    return query_fact_value(analysis.facts, "matter")


def _evaluate_normative_candidates(
    request: HybridOrchestrationRequest,
) -> tuple[list[NormativeApplicabilityResult], list[str], list[str]]:
    results: list[NormativeApplicabilityResult] = []
    evidence_refs: list[str] = []
    applicable_refs: list[str] = []
    for candidate in request.normative_candidates:
        result = evaluate_normative_applicability(
            NormativeApplicabilityRequest(
                legal_unit_id=candidate.legal_unit_id,
                version_label=candidate.version_label,
                effective_from=candidate.effective_from,
                effective_to=candidate.effective_to,
                fiscal_year=candidate.fiscal_year,
                validity_status=candidate.validity_status,
                validity_scope=candidate.validity_scope,
                validity_basis=candidate.validity_basis,
                validity_verified_at=candidate.validity_verified_at,
                official_source=candidate.official_source,
                query_date=request.query_date,
                query_fiscal_year=request.query_fiscal_year,
            )
        )
        results.append(result)
        if result.evidence_available:
            evidence_refs.append(candidate.ref)
        if result.applicable:
            applicable_refs.append(candidate.ref)
    return results, evidence_refs, applicable_refs


def _deterministic_evidence(
    normative_refs: list[str],
    rule_result: RuleEvaluationResult,
    isr_result: object | None,
    cbr_result: CBRRetrievalResult | None,
    jurisprudence_result: JurisprudenceRetrievalResult | None,
    hybrid_coordination: object | None = None,
    heuristic_evaluation: LegalHeuristicEvaluation | None = None,
) -> DeterministicEvidence:
    calculations: list[str] = []
    if isr_result is not None:
        final_tax = getattr(isr_result, "final_tax", None)
        taxable_base = getattr(isr_result, "taxable_base", None)
        calculations.append(f"ISR: taxable_base={taxable_base}; final_tax={final_tax}")

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

    heuristic_signals, heuristic_priorities, heuristic_requires_review = (
        build_heuristic_explanation_evidence(heuristic_evaluation)
    )

    return DeterministicEvidence(
        applicable_normative_refs=normative_refs,
        rule_conclusions=[
            f"{item.rule_id}@{item.version}: {item.conclusion}"
            for item in rule_result.matched_rules
        ],
        calculations=calculations,
        similar_cases=similar_cases,
        jurisprudential_criteria=jurisprudential_criteria,
        hybrid_relation=(
            getattr(getattr(hybrid_coordination, "relation", None), "value", None)
        ),
        hybrid_conclusion=getattr(hybrid_coordination, "conclusion", None),
        hybrid_controlling_source=getattr(
            hybrid_coordination, "controlling_source", None
        ),
        hybrid_reasons=list(getattr(hybrid_coordination, "reasons", [])),
        heuristic_signals=heuristic_signals,
        heuristic_priorities=heuristic_priorities,
        heuristic_requires_review=heuristic_requires_review,
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
            or bool(getattr(hybrid_coordination, "requires_review", False))
            or heuristic_requires_review
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
        legal_hypothesis_service: LegalHypothesisGeneratorLike | None = None,
        isr_tariff: ISRTariff | None = None,
        isr_tariff_registry: ISRTariffRegistry | None = None,
        cbr_cases: list[CBRCase] | None = None,
        jurisprudence_retriever: JurisprudenceRetriever | None = None,
        temporal_guard: TemporalRuntimeGuard | None = None,
    ) -> None:
        self._query_analyzer = query_analyzer
        self._retriever = retriever
        self._llm_service = llm_service
        self._rule_set = rule_set
        self._legal_hypothesis_service = legal_hypothesis_service
        self._isr_tariff = isr_tariff
        self._isr_tariff_registry = isr_tariff_registry
        self._cbr_cases = list(cbr_cases or [])
        self._jurisprudence_retriever = jurisprudence_retriever
        self._temporal_guard = temporal_guard

    def run(self, request: HybridOrchestrationRequest) -> HybridOrchestrationResult:
        traces: list[StageTrace] = []

        analysis = self._query_analyzer.analyze(request.query)
        analysis = _merge_request_context(analysis, request)
        traces.append(
            StageTrace(
                stage=OrchestrationStage.QUERY_ANALYSIS,
                status=StageStatus.COMPLETED,
                detail=f"Intento principal: {analysis.primary_intent.value}.",
            )
        )

        focused_rag_execution = None
        focused_retrieval = None
        if (
            analysis.focused_rag_plan is not None
            and analysis.focused_rag_plan.plan_applied
        ):
            focused_run = execute_focused_rag(
                analysis.normalized_query,
                plan=analysis.focused_rag_plan,
                retriever=self._retriever,
                top_k=request.top_k,
            )
            focused_retrieval = focused_run.retrieval
            focused_rag_execution = focused_run.execution

        full_corpus_expansion_execution = None
        if analysis.full_corpus_expansion_plan is not None:
            expansion_run = execute_full_corpus_expansion(
                analysis.normalized_query,
                plan=analysis.full_corpus_expansion_plan,
                retriever=self._retriever,
                top_k=request.top_k,
                focused_retrieval=focused_retrieval,
                focused_execution=focused_rag_execution,
            )
            retrieval = expansion_run.retrieval
            full_corpus_expansion_execution = expansion_run.execution
            if full_corpus_expansion_execution.expansion_applied:
                reasons = ",".join(
                    item.value
                    for item in full_corpus_expansion_execution.trigger_reasons
                )
                retrieval_detail = (
                    "RAG focal D.7 + expansión D.8: "
                    f"chunks={retrieval.returned_count}; "
                    f"fuentes={len(full_corpus_expansion_execution.hit_source_ids)}; "
                    f"razones={reasons}."
                )
            else:
                exact_count = (
                    len(focused_rag_execution.exact_seed_hit_ids)
                    if focused_rag_execution is not None
                    else 0
                )
                retrieval_detail = (
                    "RAG focal D.7; expansión D.8 no requerida: "
                    f"chunks={retrieval.returned_count}; "
                    f"fuentes={len(full_corpus_expansion_execution.hit_source_ids)}; "
                    f"exactos={exact_count}."
                )
        else:
            retrieval = self._retriever.search(
                analysis.normalized_query,
                top_k=request.top_k,
                filters=_retrieval_filters(analysis),
            )
            retrieval_detail = f"Chunks recuperados: {retrieval.returned_count}."
        traces.append(
            StageTrace(
                stage=OrchestrationStage.RETRIEVAL,
                status=StageStatus.COMPLETED,
                detail=retrieval_detail,
            )
        )

        initial_legal_hypothesis, hypothesis_trace = run_legal_hypothesis_stage(
            self._legal_hypothesis_service,
            retrieval,
        )
        traces.append(hypothesis_trace)

        rag_normative_candidates = build_normative_candidates(
            retrieval,
            temporal_guard=self._temporal_guard,
        )
        rag_normative_candidates = _filter_material_candidates(
            analysis,
            retrieval,
            rag_normative_candidates,
        )
        temporal_resolution = None
        resolved_fiscal_year = request.query_fiscal_year
        if analysis.temporal_control_plan is not None:
            temporal_resolution = resolve_temporal_query_context(
                analysis.temporal_control_plan,
                request.query_fiscal_year,
            )
            resolved_fiscal_year = temporal_resolution.resolved_fiscal_year
            if (
                resolved_fiscal_year is not None
                and not temporal_resolution.conflict
                and not any(
                    item.name.strip().casefold() == "fiscal_year"
                    for item in analysis.facts
                )
            ):
                analysis = analysis.model_copy(
                    update={
                        "facts": [
                            *analysis.facts,
                            ExtractedFact(
                                name="fiscal_year",
                                value=str(resolved_fiscal_year),
                                origin=FactOrigin.EXPLICIT,
                            ),
                        ],
                        "missing_fields": [
                            item
                            for item in analysis.missing_fields
                            if item.name.strip().casefold() != "fiscal_year"
                        ],
                    }
                )

        effective_request = request.model_copy(
            update={
                "query_fiscal_year": resolved_fiscal_year,
                "normative_candidates": [
                    *request.normative_candidates,
                    *rag_normative_candidates,
                ],
            }
        )
        (
            normative_results,
            normative_evidence_refs,
            applicable_refs,
        ) = _evaluate_normative_candidates(effective_request)
        traces.append(
            StageTrace(
                stage=OrchestrationStage.NORMATIVE,
                status=StageStatus.COMPLETED,
                detail=(
                    "Evidencia normativa conservada: "
                    f"{len(normative_evidence_refs)}; "
                    f"aplicable por motor normativo: {len(applicable_refs)}."
                ),
            )
        )

        temporal_control_execution = None
        if analysis.temporal_control_plan is not None and temporal_resolution is not None:
            temporal_control_execution = execute_temporal_control(
                plan=analysis.temporal_control_plan,
                query_date=request.query_date,
                resolution=temporal_resolution,
                retrieval=retrieval,
                candidates=effective_request.normative_candidates,
                normative_results=normative_results,
                evidence_refs=normative_evidence_refs,
                applicable_refs=applicable_refs,
                temporal_guard=self._temporal_guard,
            )
            applicable_refs = list(
                temporal_control_execution.promoted_normative_refs
            )
            temporal_status = (
                StageStatus.DEGRADED
                if temporal_control_execution.requires_human_review
                else StageStatus.COMPLETED
            )
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.TEMPORAL,
                    status=temporal_status,
                    detail=(
                        "Control temporal D.9: "
                        f"ejercicio={temporal_control_execution.resolved_query_fiscal_year}; "
                        f"promovidas={temporal_control_execution.promoted_count}; "
                        f"vigencia_desconocida="
                        f"{len(temporal_control_execution.unknown_validity_refs)}; "
                        f"conflicto={temporal_control_execution.query_temporal_conflict}; "
                        f"ambigüedad="
                        f"{temporal_control_execution.query_temporal_ambiguity}."
                    ),
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
                    jurisprudence_review or jurisprudence_result.requires_human_review
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

        # 5.3.5: los chunk_id siguen siendo la referencia externa y trazable.
        # Solo las normas que el motor normativo declaró aplicables se expanden
        # a la identidad estable documento:artículo que consumen las reglas.
        rule_normative_refs = build_rule_normative_refs(
            retrieval,
            set(applicable_refs),
        )
        rule_result = evaluate_rules(
            self._rule_set,
            fact_map,
            rule_normative_refs,
        )
        traces.append(
            StageTrace(
                stage=OrchestrationStage.RULES,
                status=StageStatus.COMPLETED,
                detail=f"Reglas activadas: {len(rule_result.matched_rules)}.",
            )
        )

        calculation_normative_refs = set(applicable_refs) | set(rule_normative_refs)
        isr_outcome = run_isr_stage(
            intent=analysis.primary_intent,
            requires_clarification=analysis.requires_clarification,
            rule_result=rule_result,
            facts=fact_map,
            structured_input=request.isr_input,
            applicable_normative_refs=calculation_normative_refs,
            tariff_registry=self._isr_tariff_registry,
            legacy_tariff=self._isr_tariff,
        )
        isr_result = isr_outcome.result
        isr_review = isr_outcome.requires_human_review
        isr_trace = None
        isr_trace_verification = None

        if (
            isr_result is not None
            and isr_outcome.rbr_authorized
            and isr_outcome.calculation_input is not None
            and isr_outcome.tariff is not None
        ):
            try:
                isr_trace = build_isr_calculation_trace(
                    isr_outcome.calculation_input,
                    isr_result,
                    isr_outcome.tariff,
                    rule_result,
                )
                isr_trace_verification = verify_isr_calculation_trace(isr_trace)
            except ISRTraceabilityError:
                isr_review = True
            else:
                if not isr_trace_verification.verified:
                    isr_review = True

        traces.append(
            StageTrace(
                stage=OrchestrationStage.ISR,
                status=isr_outcome.status,
                detail=isr_outcome.detail,
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
            cbr_review = any(item.requires_human_review for item in cbr_assessments)
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.CBR,
                    status=StageStatus.COMPLETED,
                    detail=f"Casos semejantes recuperados: {cbr_result.returned_count}.",
                )
            )

        rbs_reasoning = normalize_rbs_result(rule_result)
        cbr_reasoning = None
        hybrid_coordination = None
        coordination_review = False
        if request.cbr_query is None:
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.HYBRID_COORDINATION,
                    status=StageStatus.SKIPPED,
                    detail="Coordinación RBS-CBR omitida porque no se solicitó CBR.",
                )
            )
        else:
            cbr_reasoning = normalize_cbr_result(cbr_result, cbr_assessments)
            hybrid_coordination = coordinate_rbs_cbr(rbs_reasoning, cbr_reasoning)
            coordination_review = hybrid_coordination.requires_review
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.HYBRID_COORDINATION,
                    status=(
                        StageStatus.DEGRADED
                        if coordination_review
                        else StageStatus.COMPLETED
                    ),
                    detail=(
                        "Coordinación RBS-CBR: "
                        f"{hybrid_coordination.relation.value}; "
                        "fuente controladora="
                        f"{hybrid_coordination.controlling_source or 'ninguna'}."
                    ),
                )
            )

        heuristic_evaluation, heuristic_trace, heuristic_review = (
            run_legal_heuristics_stage(hybrid_coordination)
        )
        traces.append(heuristic_trace)

        (
            initial_legal_hypothesis_verification,
            hypothesis_verification_trace,
        ) = run_legal_hypothesis_verification_stage(
            initial_legal_hypothesis,
            rule_result=rule_result,
            hybrid_coordination=hybrid_coordination,
        )
        traces.append(hypothesis_verification_trace)

        deterministic = _deterministic_evidence(
            applicable_refs,
            rule_result,
            isr_result,
            cbr_result,
            jurisprudence_result,
            hybrid_coordination,
            heuristic_evaluation,
        )
        explanation = None
        llm_trace = None
        llm_review = False
        try:
            explanation = self._llm_service.explain(
                retrieval,
                deterministic_evidence=deterministic,
                explanation_mode=request.explanation_mode,
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
            llm_trace = build_llm_trace(
                explanation,
                explanation_mode=request.explanation_mode,
            )
            traces.append(
                StageTrace(
                    stage=OrchestrationStage.EXPLANATION,
                    status=StageStatus.COMPLETED,
                    detail=(
                        "Explicación generada con evidencia recuperada y resultados deterministas; "
                        f"modo={request.explanation_mode.value}."
                    ),
                )
            )

        normative_review = any(result.requires_human_review for result in normative_results)
        if temporal_control_execution is not None:
            normative_review = (
                normative_review or temporal_control_execution.requires_human_review
            )
        has_material_normative_evidence = any(
            _materially_relevant_hit(analysis, hit) for hit in retrieval.hits
        )
        if has_material_normative_evidence and not applicable_refs:
            normative_review = True
        explanation_review = (
            explanation.answer.requires_human_review if explanation is not None else False
        )

        return HybridOrchestrationResult(
            analysis=analysis,
            retrieval=retrieval,
            focused_rag_execution=focused_rag_execution,
            full_corpus_expansion_execution=full_corpus_expansion_execution,
            temporal_control_execution=temporal_control_execution,
            initial_legal_hypothesis=initial_legal_hypothesis,
            initial_legal_hypothesis_verification=(
                initial_legal_hypothesis_verification
            ),
            normative_candidates=effective_request.normative_candidates,
            normative_results=normative_results,
            normative_evidence_refs=normative_evidence_refs,
            applicable_normative_refs=applicable_refs,
            jurisprudence_result=jurisprudence_result,
            rule_result=rule_result,
            isr_result=isr_result,
            isr_trace=isr_trace,
            isr_trace_verification=isr_trace_verification,
            cbr_result=cbr_result,
            cbr_reuse_assessments=cbr_assessments,
            rbs_reasoning=rbs_reasoning,
            cbr_reasoning=cbr_reasoning,
            hybrid_coordination=hybrid_coordination,
            heuristic_evaluation=heuristic_evaluation,
            explanation=explanation,
            llm_trace=llm_trace,
            traces=traces,
            requires_human_review=any(
                (
                    analysis.requires_human_review,
                    normative_review,
                    rule_result.requires_human_review,
                    isr_review,
                    cbr_review,
                    coordination_review,
                    heuristic_review,
                    jurisprudence_review,
                    llm_review,
                    explanation_review,
                )
            ),
        )
