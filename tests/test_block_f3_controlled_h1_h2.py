from __future__ import annotations

import json
from datetime import date

import pytest

from app.domain.hybrid_llama_hypotheses import (
    HybridLlamaHypothesisKind,
)
from app.domain.jurisprudence import JurisprudenceCriterionType
from app.domain.jurisprudence_ratio import JurisprudenceRatioSourceSection
from app.domain.llama_hybrid_context import (
    InitialFiscalHypothesisContext,
    JurisprudentialRatioContext,
    LlamaFactSnapshot,
    LlamaHeuristicRouteContext,
)
from app.domain.orchestration import HybridOrchestrationResult
from app.domain.query import FactOrigin, QueryIntent
from app.services.hybrid_contract_baseline import audit_current_hybrid_contracts
from app.services.hybrid_hypothesis_generation import (
    LlamaFiscalHypothesisH1Service,
    LlamaJurisprudentialRatioH2Service,
)
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from llm.errors import LLMResponseValidationError
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request


class StaticMessageProvider:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.calls = 0
        self.messages: list[dict[str, str]] | None = None
        self.schema: dict[str, object] | None = None

    @property
    def provider_name(self) -> str:
        return "f3-static"

    @property
    def model_name(self) -> str:
        return "llama-f3-test"

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        self.calls += 1
        self.messages = messages
        self.schema = response_schema
        return json.dumps(self.payload, ensure_ascii=False)


def _h1_context() -> InitialFiscalHypothesisContext:
    return InitialFiscalHypothesisContext(
        question="¿Puedo permanecer en RESICO si excedí el límite de ingresos?",
        normalized_query="puedo permanecer resico excedi limite ingresos",
        primary_intent=QueryIntent.INTERPRET_PROVISION,
        facts=[
            LlamaFactSnapshot(
                name="fiscal_regime",
                value="RESICO",
                origin=FactOrigin.EXPLICIT,
            ),
            LlamaFactSnapshot(
                name="issue",
                value="límite de ingresos",
                origin=FactOrigin.EXPLICIT,
            ),
        ],
        missing_fields=[],
        ambiguities=[],
        heuristic_route=LlamaHeuristicRouteContext(
            primary_problem_id="determinacion_regimen",
            primary_problem_label="Determinación del régimen fiscal aplicable",
            primary_institution_id="resico_personas_fisicas",
            primary_institution_label="Régimen Simplificado de Confianza",
            normative_focus_source_ids=["lisr"],
            exact_normative_hints=["lisr:articulo_113_e"],
        ),
    )


def _valid_h1_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "legal_problem": "Determinar si el exceso del límite altera la permanencia en RESICO.",
        "proposition": (
            "El exceso del límite podría modificar el régimen fiscal aplicable y debe "
            "contrastarse con la normativa vigente y los motores jurídicos posteriores."
        ),
        "facts_used": [
            {
                "name": "fiscal_regime",
                "value": "RESICO",
                "origin": "explicit",
            },
            {
                "name": "issue",
                "value": "límite de ingresos",
                "origin": "explicit",
            },
        ],
        "institutions": ["resico_personas_fisicas"],
        "candidate_normative_refs": ["lisr:articulo_113_e"],
        "candidate_normative_questions": [
            "¿Qué condición normativa regula la permanencia en el régimen?"
        ],
        "assumptions": ["El contribuyente es persona física."],
        "uncertainties": [],
        "confidence": 0.62,
        "requires_validation": True,
        "changes_deterministic_result": False,
        "can_control_legal_decision": False,
        "asserts_external_legal_authority": False,
    }
    payload.update(overrides)
    return payload


def _h2_context() -> JurisprudentialRatioContext:
    justification = (
        "El límite de ingresos constituye una condición sustantiva para permanecer en el "
        "régimen. Una vez excedido durante el ejercicio, el contribuyente deja de reunir "
        "la característica económica prevista para ese ejercicio y debe tributar conforme "
        "al capítulo que corresponda a partir del mes siguiente. La regla administrativa "
        "no modifica esa condición legal, sino que refleja su operación anual."
    )
    return JurisprudentialRatioContext(
        document_id="jurisprudencia-2032043",
        source_sha256="a" * 64,
        criterion_type=JurisprudenceCriterionType.JURISPRUDENCE,
        facts_text=(
            "Una persona física excedió el límite de ingresos del régimen y controvirtió "
            "la regla administrativa aplicable."
        ),
        legal_criterion_text=(
            "La regla administrativa no vulnera la subordinación jerárquica porque refleja "
            "las características legales del régimen."
        ),
        justification_text=justification,
        facts_source_pages=[1],
        legal_criterion_source_pages=[1],
        justification_source_pages=[1],
        candidate_normative_refs=["lisr:articulo_113_e"],
        material_relation_types=["interprets"],
        binding_character_mandatory=True,
        binding_from=date(2026, 4, 20),
        e5_authorized_for_evidence=True,
    )


def _valid_h2_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "legal_question": (
            "¿Qué efecto produce exceder el límite de ingresos sobre la permanencia en el régimen?"
        ),
        "material_facts": [
            "La persona física excedió el límite de ingresos durante el ejercicio."
        ],
        "interpreted_norms": ["lisr:articulo_113_e"],
        "essential_premises": [
            "El límite de ingresos es una condición sustantiva del régimen.",
            "Excederlo elimina la característica económica exigida para ese ejercicio.",
        ],
        "proposed_ratio": (
            "Cuando se excede durante el ejercicio el límite de ingresos que funciona como "
            "condición sustantiva del régimen, deja de satisfacerse la característica "
            "económica necesaria para permanecer en él y procede tributar conforme al "
            "régimen correspondiente desde el mes siguiente."
        ),
        "possible_obiter": [
            "La referencia a la operación anual de la regla administrativa es contextual."
        ],
        "supporting_spans": [
            {
                "text": (
                    "El límite de ingresos constituye una condición sustantiva para permanecer "
                    "en el régimen."
                ),
                "page": 1,
                "source_section": "justification",
            },
            {
                "text": (
                    "Una vez excedido durante el ejercicio, el contribuyente deja de reunir "
                    "la característica económica prevista para ese ejercicio"
                ),
                "page": 1,
                "source_section": "justification",
            },
        ],
        "uncertainties": [],
        "confidence": 0.84,
        "requires_validation": True,
        "changes_deterministic_result": False,
        "can_control_legal_decision": False,
        "asserts_external_legal_authority": False,
    }
    payload.update(overrides)
    return payload


def test_f3_h1_is_generated_from_early_context_as_non_authoritative_hypothesis() -> None:
    provider = StaticMessageProvider(_valid_h1_payload())

    result = LlamaFiscalHypothesisH1Service(provider).generate(_h1_context())

    assert result.generation_performed is True
    assert result.hypothesis is not None
    assert result.hypothesis.kind is HybridLlamaHypothesisKind.H1_FISCAL
    assert result.hypothesis.hypothesis_id.startswith("H1-")
    assert result.hypothesis.must_be_contrasted_with_rbs is True
    assert result.hypothesis.must_be_contrasted_with_cbr is True
    assert result.hypothesis.normative_validation_pending is True
    assert result.hypothesis.can_control_legal_decision is False
    assert result.hypothesis.changes_deterministic_result is False
    assert "f3:h1:rbs_result_used=false" in result.trace
    assert "f3:h1:cbr_result_used=false" in result.trace


def test_f3_h1_prompt_explicitly_excludes_downstream_authority() -> None:
    provider = StaticMessageProvider(_valid_h1_payload())

    LlamaFiscalHypothesisH1Service(provider).generate(_h1_context())

    assert provider.messages is not None
    system = provider.messages[0]["content"]
    user = provider.messages[1]["content"]
    assert "hipótesis fiscal inicial" in system
    assert "No inventes hechos, artículos, jurisprudencia" in system
    assert '"rbs_result_available":false' in user
    assert '"cbr_result_available":false' in user
    assert '"jurisprudence_ratio_available":false' in user


def test_f3_h1_rejects_fact_not_present_in_early_context() -> None:
    provider = StaticMessageProvider(
        _valid_h1_payload(
            facts_used=[
                {
                    "name": "income",
                    "value": "5000000",
                    "origin": "explicit",
                }
            ]
        )
    )

    with pytest.raises(LLMResponseValidationError, match="hechos fuera del contexto"):
        LlamaFiscalHypothesisH1Service(provider).generate(_h1_context())


def test_f3_h1_rejects_normative_ref_not_authorized_as_heuristic_hint() -> None:
    provider = StaticMessageProvider(
        _valid_h1_payload(candidate_normative_refs=["cff:articulo_999"])
    )

    with pytest.raises(LLMResponseValidationError, match="referencia normativa"):
        LlamaFiscalHypothesisH1Service(provider).generate(_h1_context())


def test_f3_h1_rejects_specific_authority_assertion_in_proposition() -> None:
    provider = StaticMessageProvider(
        _valid_h1_payload(
            proposition="El artículo 999 obliga definitivamente al contribuyente."
        )
    )

    with pytest.raises(LLMResponseValidationError, match="cita jurídica específica"):
        LlamaFiscalHypothesisH1Service(provider).generate(_h1_context())


def test_f3_h1_identifier_is_deterministic_for_same_context_and_draft() -> None:
    first = LlamaFiscalHypothesisH1Service(
        StaticMessageProvider(_valid_h1_payload())
    ).generate(_h1_context())
    second = LlamaFiscalHypothesisH1Service(
        StaticMessageProvider(_valid_h1_payload())
    ).generate(_h1_context())

    assert first.hypothesis is not None
    assert second.hypothesis is not None
    assert first.hypothesis.hypothesis_id == second.hypothesis.hypothesis_id
    assert first.hypothesis.source_context_sha256 == second.hypothesis.source_context_sha256


def test_f3_h2_is_reconstructed_from_justification_with_traceable_support() -> None:
    provider = StaticMessageProvider(_valid_h2_payload())

    result = LlamaJurisprudentialRatioH2Service(provider).generate(_h2_context())

    assert result.generation_performed is True
    assert result.ratio is not None
    assert result.ratio.kind is HybridLlamaHypothesisKind.H2_JURISPRUDENTIAL_RATIO
    assert result.ratio.ratio_id.startswith("H2-")
    assert result.ratio.document_id == "jurisprudencia-2032043"
    assert result.ratio.ratio_source_section is JurisprudenceRatioSourceSection.JUSTIFICATION
    assert result.ratio.justification_source_pages == [1]
    assert result.ratio.interpreted_norms == ["lisr:articulo_113_e"]
    assert result.ratio.ratio_material_delimitation_completed is False
    assert result.ratio.legal_applicability_evaluated is False
    assert result.ratio.can_control_legal_decision is False
    assert result.requires_human_review is True
    assert "f3:h2:ratio_subset_of_justification=true" in result.trace


def test_f3_h2_prompt_defines_ratio_as_subset_and_requires_counterfactual_test() -> None:
    provider = StaticMessageProvider(_valid_h2_payload())

    LlamaJurisprudentialRatioH2Service(provider).generate(_h2_context())

    assert provider.messages is not None
    system = provider.messages[0]["content"]
    system_normalized = " ".join(system.split())
    user = provider.messages[1]["content"]
    assert "subconjunto de premisas indispensables" in system_normalized
    assert "no equipares toda la Justificación" in system
    assert "contrafactual" in system
    assert '"ratio_rule":"ratio_subset_of_justification"' in user
    assert '"applicability_evaluation_requested":false' in user


def test_f3_h2_rejects_support_span_outside_justification() -> None:
    provider = StaticMessageProvider(
        _valid_h2_payload(
            supporting_spans=[
                {
                    "text": "Este fragmento fue inventado por el modelo.",
                    "page": 1,
                    "source_section": "justification",
                }
            ]
        )
    )

    with pytest.raises(LLMResponseValidationError, match="no pertenece a la Justificación"):
        LlamaJurisprudentialRatioH2Service(provider).generate(_h2_context())


def test_f3_h2_rejects_support_page_outside_justification_trace() -> None:
    provider = StaticMessageProvider(
        _valid_h2_payload(
            supporting_spans=[
                {
                    "text": (
                        "El límite de ingresos constituye una condición sustantiva para "
                        "permanecer en el régimen."
                    ),
                    "page": 2,
                    "source_section": "justification",
                }
            ]
        )
    )

    with pytest.raises(LLMResponseValidationError, match="página fuera de la Justificación"):
        LlamaJurisprudentialRatioH2Service(provider).generate(_h2_context())


def test_f3_h2_rejects_norm_not_identified_by_jurisprudence_relation_stage() -> None:
    provider = StaticMessageProvider(
        _valid_h2_payload(interpreted_norms=["cff:articulo_1"])
    )

    with pytest.raises(LLMResponseValidationError, match="norma fuera de las relaciones"):
        LlamaJurisprudentialRatioH2Service(provider).generate(_h2_context())


def test_f3_h2_identifier_is_deterministic_and_does_not_evaluate_applicability() -> None:
    first = LlamaJurisprudentialRatioH2Service(
        StaticMessageProvider(_valid_h2_payload())
    ).generate(_h2_context())
    second = LlamaJurisprudentialRatioH2Service(
        StaticMessageProvider(_valid_h2_payload())
    ).generate(_h2_context())

    assert first.ratio is not None
    assert second.ratio is not None
    assert first.ratio.ratio_id == second.ratio.ratio_id
    assert first.ratio.source_context_sha256 == second.ratio.source_context_sha256
    assert first.ratio.controversy_equivalence_evaluated is False
    assert first.ratio.material_facts_equivalence_evaluated is False


def test_f3_result_contract_adds_h1_h2_channels_without_runtime_activation() -> None:
    fields = HybridOrchestrationResult.model_fields
    baseline = _orchestrator(None).run(_request())

    assert "llama_fiscal_hypothesis_h1" in fields
    assert "llama_jurisprudential_ratio_h2" in fields
    assert baseline.llama_fiscal_hypothesis_h1 is None
    assert baseline.llama_jurisprudential_ratio_h2 == []


def test_f3_h1_h2_objects_do_not_change_analyzer_or_legal_decision() -> None:
    baseline = _orchestrator(None).run(_request())
    h1 = LlamaFiscalHypothesisH1Service(
        StaticMessageProvider(_valid_h1_payload())
    ).generate(_h1_context())
    h2 = LlamaJurisprudentialRatioH2Service(
        StaticMessageProvider(_valid_h2_payload())
    ).generate(_h2_context())
    enriched = baseline.model_copy(
        update={
            "llama_fiscal_hypothesis_h1": h1,
            "llama_jurisprudential_ratio_h2": [h2],
        }
    )

    baseline_analysis = build_integral_legal_analysis(baseline)
    enriched_analysis = build_integral_legal_analysis(enriched)
    baseline_decision = build_legal_decision(baseline_analysis)
    enriched_decision = build_legal_decision(enriched_analysis)

    assert enriched_analysis == baseline_analysis
    assert enriched_decision == baseline_decision


def test_f3_preserves_f1_contracts_and_does_not_activate_real_llm() -> None:
    audit = audit_current_hybrid_contracts()

    assert audit.all_contracts_preserved is True
    assert audit.real_llm_activation_performed is False
    assert audit.h1_h2_runtime_activation_performed is False
    assert audit.runtime_order_changed is False
    assert audit.legal_decision_changed is False
