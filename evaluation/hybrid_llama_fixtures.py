from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.domain.cbr import CaseStatus, CBRCase, CBRQuery
from app.domain.chunks import ChunkMetadata, LegalChunkType, LegalHierarchy
from app.domain.documents import SourceType
from app.domain.isr import ISRBracket, ISRCalculationInput, ISRPeriod, ISRTariff
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.orchestration import HybridOrchestrationRequest, NormativeCandidate
from app.domain.query import ExtractedFact, QueryAnalysis, QueryIntent
from app.domain.rules import RuleCondition, RuleDefinition, RuleOperator, RuleSet
from app.services.hybrid_hypothesis_generation import LlamaFiscalHypothesisH1Service
from app.services.hybrid_llama_runtime import (
    HybridLlamaRuntime,
    build_hybrid_llama_service_bundle,
)
from app.services.hybrid_orchestrator import HybridOrchestrator
from app.services.jurisprudence_metadata_extraction import (
    extract_jurisprudence_metadata_record,
)
from app.services.jurisprudence_normative_relations import (
    build_jurisprudence_normative_relation_record,
)
from app.services.jurisprudence_ratio import build_jurisprudence_ratio_record
from app.services.jurisprudence_temporal_control import (
    build_jurisprudence_temporal_record,
)
from llm.errors import LLMGenerationError
from llm.models import LLMGenerationContext
from llm.service import LlamaRAGService
from rag.retrieval.filters import RetrievalFilters
from rag.retrieval.models import RetrievalHit, RetrievalResult

_REFERENCE_NORM = "NORM_TEST_ISR_2026"
_REFERENCE_CONCLUSION = "Perfil sujeto a revisión ISR."
_JURISPRUDENCE_DOCUMENT_ID = "tesis-2032043-f12"
_JURISPRUDENCE_SHA = "f" * 64
_JURISPRUDENCE_TEXT = """Registro digital: 2032043
RÉGIMEN SIMPLIFICADO DE CONFIANZA PARA PERSONAS FÍSICAS EN EL IMPUESTO
SOBRE LA RENTA (RESICO). LA REGLA 3.13.33. DE LA RESOLUCIÓN MISCELÁNEA FISCAL
PARA 2023 NO VIOLA EL PRINCIPIO DE SUBORDINACIÓN JERÁRQUICA.
Hechos: Una persona física impugnó la regla 3.13.33. de la RMF 2023 porque estimó
que contravenía el artículo 113-E de la Ley del Impuesto sobre la Renta.
Criterio jurídico: La regla 3.13.33. de la Resolución Miscelánea Fiscal para 2023
no viola el principio de subordinación jerárquica.
Justificación: Conforme al artículo 113-E de la Ley del Impuesto sobre la Renta,
el límite de ingresos es una condición sustantiva del RESICO. Una vez superado el
límite económico, su artículo 113-E debe leerse en el sentido de que la persona ya
no reúne la característica económica del RESICO para ese ejercicio fiscal.
Instancia: Pleno
Materia(s): Constitucional
Tesis: P./J. 58/2026 (12a.)
Fuente: Semanario Judicial de la Federación.
Tipo: Jurisprudencia
Publicación: viernes 17 de abril de 2026 10:21 h
Esta tesis se publicó el viernes 17 de abril de 2026 a las 10:21 horas en el
Semanario Judicial de la Federación y, por ende, se considera de aplicación
obligatoria a partir del lunes 20 de abril de 2026.
"""


class F12BenchmarkProvider(Protocol):
    """Contrato común F.12: explicación RAG + generación estructurada H1/H2/verificador."""

    @property
    def provider_name(self) -> str:
        ...

    @property
    def model_name(self) -> str:
        ...

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        ...

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        ...


class BenchmarkAnalyzer:
    def __init__(self, analysis: QueryAnalysis) -> None:
        self._analysis = analysis

    def analyze(self, query: str) -> QueryAnalysis:
        del query
        return self._analysis


class BenchmarkRetriever:
    def __init__(self, result: RetrievalResult) -> None:
        self._result = result
        self.last_filters: RetrievalFilters | None = None

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filters: RetrievalFilters | None = None,
    ) -> RetrievalResult:
        del query, top_k
        self.last_filters = filters
        return self._result


class F12ReferenceStructuredProvider:
    """Baseline determinista de evaluación; jamás se usa como runtime productivo."""

    @property
    def provider_name(self) -> str:
        return "f12-reference-test-double"

    @property
    def model_name(self) -> str:
        return "f12-reference-structured"

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        deterministic = context.deterministic_evidence
        return json.dumps(
            {
                "summary": "Explicación F.12 basada en evidencia determinista.",
                "analysis": "La explicación no modifica la conclusión determinista.",
                "evidence_ids": [item.chunk_id for item in context.evidence[:2]],
                "normative_refs": (
                    list(deterministic.applicable_normative_refs)
                    if deterministic is not None
                    else []
                ),
                "rule_refs": (
                    list(deterministic.rule_conclusions)
                    if deterministic is not None
                    else []
                ),
                "calculation_refs": (
                    list(deterministic.calculations)
                    if deterministic is not None
                    else []
                ),
                "cbr_refs": (
                    list(deterministic.similar_cases)
                    if deterministic is not None
                    else []
                ),
                "jurisprudence_refs": (
                    list(deterministic.jurisprudential_criteria)
                    if deterministic is not None
                    else []
                ),
                "uncertainties": [],
                "requires_human_review": bool(
                    deterministic is not None and deterministic.requires_human_review
                ),
                "changes_deterministic_result": False,
                "asserts_external_legal_authority": False,
            },
            ensure_ascii=False,
        )

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        del response_schema
        payload = json.loads(messages[-1]["content"])
        task = str(payload["task"])
        if task == "explicar_rag_controlado_compacto":
            catalog = payload["selection_catalog"]
            deterministic = payload.get("deterministic_summary") or {}
            return json.dumps(
                {
                    "summary": "Explicación F.12 basada en evidencia determinista.",
                    "analysis": "La explicación no modifica la conclusión determinista.",
                    "evidence_indices": [0] if catalog.get("evidence_ids") else [],
                    "normative_ref_indices": (
                        [0] if catalog.get("normative_refs") else []
                    ),
                    "rule_ref_indices": [0] if catalog.get("rule_refs") else [],
                    "calculation_ref_indices": (
                        [0] if catalog.get("calculation_refs") else []
                    ),
                    "cbr_ref_indices": [0] if catalog.get("cbr_refs") else [],
                    "jurisprudence_ref_indices": (
                        [0] if catalog.get("jurisprudence_refs") else []
                    ),
                    "uncertainty_note": None,
                    "requires_human_review": bool(
                        deterministic.get("requires_human_review", False)
                    ),
                },
                ensure_ascii=False,
            )
        if task == "formular_h1_fiscal_inicial_controlada":
            catalog = payload["selection_catalog"]
            facts = list(catalog.get("facts", []))
            institutions = list(catalog.get("institutions", []))
            normative_refs = list(catalog.get("normative_refs", []))
            return json.dumps(
                {
                    "legal_problem": "Determinar la consecuencia fiscal controlada.",
                    "proposition": _REFERENCE_CONCLUSION,
                    "fact_indices": list(range(min(2, len(facts)))),
                    "institution_indices": [0] if institutions else [],
                    "normative_ref_indices": [0] if normative_refs else [],
                    "confidence_band": "medium",
                },
                ensure_ascii=False,
            )
        if task == "formular_h2_ratio_decidendi_controlada":
            catalog = payload["selection_catalog"]
            support_spans = list(catalog.get("support_spans", []))
            normative_refs = list(catalog.get("normative_refs", []))
            return json.dumps(
                {
                    "legal_question": "¿Cuál es la premisa indispensable del criterio?",
                    "normative_ref_indices": [0] if normative_refs else [],
                    "support_span_indices": [0] if support_spans else [],
                    "proposed_ratio": (
                        "La ratio propuesta queda limitada a la premisa indispensable "
                        "anclada en la Justificación."
                    ),
                    "obiter_span_indices": [],
                    "confidence_band": "high",
                },
                ensure_ascii=False,
            )
        if task == "verificar_argumento_hibrido_sin_redecidir":
            packet = payload["packet"]
            h1_present = packet.get("h1") is not None
            h2_items = {
                str(index): {
                    "source_fidelity": "consistent",
                    "consistency_with_coordinated_argument": "consistent",
                }
                for index, _item in enumerate(packet.get("h2", []))
            }
            binding = bool(
                packet.get("binding_jurisprudence", {}).get(
                    "applicable_document_ids", []
                )
            )
            return json.dumps(
                {
                    "h1_consistency": "consistent" if h1_present else "not_applicable",
                    "rbs_representation": "consistent",
                    "cbr_role": "consistent",
                    "h2_assessments": h2_items,
                    "binding_jurisprudence_consistency": (
                        "consistent" if binding else "not_applicable"
                    ),
                    "contradiction_codes": [],
                    "hallucination_signals": [],
                    "requires_human_review": False,
                },
                ensure_ascii=False,
            )
        raise LLMGenerationError(f"Tarea F.12 inesperada: {task}")


def _analysis() -> QueryAnalysis:
    return QueryAnalysis(
        original_query="Calcula ISR 2026 para una persona física.",
        normalized_query="Calcula ISR 2026 para una persona física.",
        primary_intent=QueryIntent.CALCULATE_ISR,
        facts=[
            ExtractedFact(name="fiscal_year", value="2026"),
            ExtractedFact(name="taxpayer_type", value="individual"),
        ],
        requires_clarification=False,
    )


def _retrieval() -> RetrievalResult:
    metadata = ChunkMetadata(
        document_id="normativa-f12",
        source_type=SourceType.NORMATIVA,
        source_filename="norma-f12.md",
        chunk_index=0,
        chunk_type=LegalChunkType.ARTICLE,
        legal_identifier="Artículo F.12",
        page_start=1,
        page_end=1,
        hierarchy=LegalHierarchy(article="Artículo F.12"),
        source_sha256="a" * 64,
        fiscal_year=2026,
        version_label="2026-A",
    )
    return RetrievalResult(
        query="Calcula ISR",
        requested_top_k=5,
        candidate_count=1,
        returned_count=1,
        hits=[
            RetrievalHit(
                rank=1,
                score=0.95,
                chunk_id="normativa-f12-chunk-00001",
                text="Evidencia normativa sintética controlada F.12.",
                metadata=metadata,
            )
        ],
    )


def _rules() -> RuleSet:
    return RuleSet(
        schema_version="1.0",
        rules=[
            RuleDefinition(
                rule_id="ISR_RULE_F12_001",
                version="1.0",
                description="Regla sintética de benchmark F.12.",
                conditions=[
                    RuleCondition(
                        fact="taxpayer_type",
                        operator=RuleOperator.EQ,
                        value="individual",
                    )
                ],
                conclusion_code="isr_profile",
                conclusion=_REFERENCE_CONCLUSION,
                normative_refs=[_REFERENCE_NORM],
            )
        ],
    )


def _tariff() -> ISRTariff:
    return ISRTariff(
        schema_version="1.0",
        version="F12-1.0",
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        normative_ref=_REFERENCE_NORM,
        source_reference="F12_FIXTURE_ONLY",
        verified=True,
        brackets=[
            ISRBracket(
                lower_limit=Decimal("0"),
                upper_limit=Decimal("10000"),
                fixed_fee=Decimal("0"),
                rate_percent=Decimal("10"),
            ),
            ISRBracket(
                lower_limit=Decimal("10000.01"),
                upper_limit=None,
                fixed_fee=Decimal("1000"),
                rate_percent=Decimal("20"),
            ),
        ],
    )


def _isr_input() -> ISRCalculationInput:
    return ISRCalculationInput(
        fiscal_year=2026,
        period=ISRPeriod.ANNUAL,
        gross_income=Decimal("20000"),
        exempt_income=Decimal("1000"),
        authorized_deductions=Decimal("2000"),
        credits=Decimal("100"),
        normative_ref=_REFERENCE_NORM,
    )


def _candidate() -> NormativeCandidate:
    return NormativeCandidate(
        ref=_REFERENCE_NORM,
        legal_unit_id=1,
        version_label="2026-A",
        effective_from=date(2026, 1, 1),
        effective_to=date(2026, 12, 31),
        fiscal_year=2026,
    )


def _cbr_case() -> CBRCase:
    return CBRCase(
        case_id="CASE-F12-001",
        status=CaseStatus.ACTIVE,
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        procedural_stage="orientacion",
        fiscal_year=2026,
        resolution_summary=_REFERENCE_CONCLUSION,
        normative_refs=[_REFERENCE_NORM],
        source_refs=["F12_BENCHMARK"],
    )


def _cbr_query() -> CBRQuery:
    return CBRQuery(
        taxpayer_type="individual",
        activity="servicios profesionales",
        tax="ISR",
        problem_type="determinacion de obligaciones",
        procedural_stage="orientacion",
        fiscal_year=2026,
    )


def _jurisprudence_document() -> JurisprudenceDocumentRepresentation:
    return JurisprudenceDocumentRepresentation(
        document_id=_JURISPRUDENCE_DOCUMENT_ID,
        original_filename="Tesis2032043-F12.pdf",
        source_sha256=_JURISPRUDENCE_SHA,
        page_count=1,
        extracted_characters=len(_JURISPRUDENCE_TEXT),
        pages=[
            JurisprudencePage(
                number=1,
                text=_JURISPRUDENCE_TEXT,
                has_extractable_text=True,
            )
        ],
        full_text=_JURISPRUDENCE_TEXT,
    )


def build_f12_request(*, with_jurisprudence: bool) -> HybridOrchestrationRequest:
    request = HybridOrchestrationRequest(
        query="Calcula ISR 2026 para una persona física.",
        query_date=date(2026, 9, 4),
        query_fiscal_year=2026,
        normative_candidates=[_candidate()],
        isr_input=_isr_input(),
        cbr_query=_cbr_query(),
    )
    if not with_jurisprudence:
        return request

    document = _jurisprudence_document()
    metadata = extract_jurisprudence_metadata_record(document)
    relations = build_jurisprudence_normative_relation_record(
        document,
        metadata_record=metadata,
    )
    temporal = build_jurisprudence_temporal_record(metadata)
    ratio = build_jurisprudence_ratio_record(metadata)
    return request.model_copy(
        update={
            "query": "RESICO límite de ingresos artículo 113-E",
            "session_jurisprudence_documents": [document],
            "session_jurisprudence_metadata": {
                document.document_id: metadata.extracted
            },
            "session_jurisprudence_normative_relations": {
                document.document_id: relations
            },
            "session_jurisprudence_temporal_records": {
                document.document_id: temporal
            },
            "session_jurisprudence_ratio_records": {
                document.document_id: ratio
            },
        },
        deep=True,
    )


def build_f12_runtime(
    provider: F12BenchmarkProvider,
    *,
    provider_is_test_double: bool,
) -> HybridLlamaRuntime:
    services = build_hybrid_llama_service_bundle(provider)
    h1_service: LlamaFiscalHypothesisH1Service = services.h1
    orchestrator = HybridOrchestrator(
        query_analyzer=BenchmarkAnalyzer(_analysis()),
        retriever=BenchmarkRetriever(_retrieval()),
        llm_service=LlamaRAGService(provider),
        rule_set=_rules(),
        isr_tariff=_tariff(),
        cbr_cases=[_cbr_case()],
        hybrid_h1_service=h1_service,
    )
    return HybridLlamaRuntime(
        orchestrator=orchestrator,
        services=services,
        provider_is_test_double=provider_is_test_double,
    )
