from __future__ import annotations

import json

from app.domain.hybrid_legal_verification import (
    HybridLegalSemanticVerificationDraft,
    HybridLegalVerificationState,
    HybridSemanticAssessment,
)
from app.domain.jurisprudence_decision_application import JurisprudenceDecisionEffect
from app.domain.orchestration import HybridOrchestrationResult
from app.services.cbr_h1_contrast import contrast_h1_with_cbr
from app.services.cbr_reasoning import assess_case_reuse
from app.services.hybrid_contract_baseline import audit_current_hybrid_contracts
from app.services.hybrid_hypothesis_generation import (
    LlamaFiscalHypothesisH1Service,
    LlamaJurisprudentialRatioH2Service,
)
from app.services.hybrid_legal_coordination import coordinate_hybrid_legal_argument
from app.services.hybrid_legal_semantic_verifier import LlamaHybridLegalVerificationService
from app.services.hybrid_legal_verification import (
    build_hybrid_legal_verification_packet,
    hybrid_verification_packet_sha256,
    verify_hybrid_legal_argument,
)
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.legal_decision import build_legal_decision
from app.services.rbs_h1_contrast import contrast_h1_with_rbs
from cbr.engine import retrieve_similar_cases
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request
from tests.test_block_f3_controlled_h1_h2 import (
    StaticMessageProvider,
    _h1_context,
    _h2_context,
    _valid_h1_payload,
    _valid_h2_payload,
)
from tests.test_block_f4_rbs_h1_determinative_contrast import _rules
from tests.test_block_f5_cbr_h1_analogical_contrast import _case, _query
from tests.test_block_f6_hybrid_legal_coordination import (
    NORM_REF,
    _application,
    _existing_coordination,
)


class StaticVerificationProvider:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.messages: list[dict[str, str]] | None = None
        self.schema: dict[str, object] | None = None

    @property
    def provider_name(self) -> str:
        return "f7-static"

    @property
    def model_name(self) -> str:
        return "llama-f7-test"

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        self.messages = messages
        self.schema = response_schema
        return json.dumps(self.payload, ensure_ascii=False)


def _generated_h1(proposition: str = "Debe abandonar el régimen."):
    provider = StaticMessageProvider(_valid_h1_payload(proposition=proposition))
    return LlamaFiscalHypothesisH1Service(provider).generate(_h1_context())


def _generated_h2():
    return LlamaJurisprudentialRatioH2Service(
        StaticMessageProvider(_valid_h2_payload())
    ).generate(_h2_context())


def _cbr_contrast(h1, resolution: str):
    cases = [_case("CASE-F7-001", resolution)]
    retrieval = retrieve_similar_cases(_query(), cases)
    assessments = [
        assess_case_reuse(match, current_normative_refs={NORM_REF})
        for match in retrieval.matches
    ]
    return contrast_h1_with_cbr(
        h1,
        cbr_result=retrieval,
        reuse_assessments=assessments,
    )


def _h1_packet(*, semantic_ready: bool = True):
    proposition = "Debe abandonar el régimen."
    h1 = _generated_h1(proposition)
    rbs = contrast_h1_with_rbs(
        h1,
        rule_result=_rules(proposition, normative_refs=[NORM_REF]),
    )
    cbr = _cbr_contrast(h1, proposition)
    coordination = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=_existing_coordination(proposition),
        h1_result=h1,
        rbs_h1_contrast=rbs,
        cbr_h1_contrast=cbr,
    )
    packet = build_hybrid_legal_verification_packet(
        coordination=coordination,
        initial_context=_h1_context(),
        h1_result=h1,
        rbs_h1_contrast=rbs,
        cbr_h1_contrast=cbr,
    )
    if semantic_ready:
        return packet
    return packet.model_copy(update={"coordination": None})


def _binding_packet():
    h2 = _generated_h2()
    application = _application(JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION)
    coordination = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=_existing_coordination(),
        h2_results=[h2],
        jurisprudence_application=application,
    )
    return build_hybrid_legal_verification_packet(
        coordination=coordination,
        h2_results=[h2],
        jurisprudence_ratio_contexts=[_h2_context()],
        jurisprudence_application=application,
    )


def _semantic_payload(packet, **overrides: object) -> dict[str, object]:
    h1_present = bool(
        packet.h1_result is not None
        and packet.h1_result.generation_performed
        and packet.h1_result.hypothesis is not None
    )
    h2_items = [
        {
            "ratio_id": item.ratio.ratio_id,
            "source_fidelity": "consistent",
            "consistency_with_coordinated_argument": "consistent",
        }
        for item in packet.h2_results
        if item.generation_performed and item.ratio is not None
    ]
    binding = bool(
        packet.jurisprudence_application is not None
        and packet.jurisprudence_application.applicable_document_ids
    )
    payload: dict[str, object] = {
        "packet_sha256": hybrid_verification_packet_sha256(packet),
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
        "changes_canonical_conclusion": False,
        "introduces_new_facts": False,
        "introduces_new_normative_refs": False,
        "introduces_external_jurisprudence": False,
        "can_control_legal_decision": False,
    }
    payload.update(overrides)
    return payload


def _semantic_draft(packet, **overrides: object) -> HybridLegalSemanticVerificationDraft:
    return HybridLegalSemanticVerificationDraft.model_validate(
        _semantic_payload(packet, **overrides)
    )


def test_f7_clean_deterministic_chain_without_h1_h2_is_verified() -> None:
    coordination = coordinate_hybrid_legal_argument(
        applicable_normative_refs=[NORM_REF],
        existing_coordination=_existing_coordination(),
    )
    packet = build_hybrid_legal_verification_packet(coordination=coordination)

    result = verify_hybrid_legal_argument(packet)

    assert result.state is HybridLegalVerificationState.VERIFIED
    assert result.normative_basis_preserved is True
    assert result.rbs_priority_preserved is True
    assert result.cbr_experiential_role_preserved is True
    assert result.binding_jurisprudence_respected is True
    assert result.single_conclusion_preserved is True
    assert result.semantic_verification_performed is False
    assert result.requires_human_review is False


def test_f7_missing_f6_coordination_fails_closed_to_human_review() -> None:
    packet = build_hybrid_legal_verification_packet(coordination=None)

    result = verify_hybrid_legal_argument(packet)

    assert result.state is HybridLegalVerificationState.HUMAN_REVIEW
    assert "f6_coordination_missing" in result.review_codes
    assert result.canonical_conclusion is None


def test_f7_h1_without_semantic_verifier_remains_human_review() -> None:
    packet = _h1_packet()

    result = verify_hybrid_legal_argument(packet)

    assert result.state is HybridLegalVerificationState.HUMAN_REVIEW
    assert "semantic_verification_pending" in result.review_codes
    assert result.h1_context_integrity_verified is True
    assert result.h1_fact_boundary_verified is True
    assert result.h1_normative_boundary_verified is True


def test_f7_consistent_semantic_verifier_can_close_h1_chain_without_mutation() -> None:
    packet = _h1_packet()
    draft = _semantic_draft(packet)

    result = verify_hybrid_legal_argument(
        packet,
        semantic_draft=draft,
        semantic_verifier_provider="f7-static",
        semantic_verifier_model="llama-f7-test",
    )

    assert result.state is HybridLegalVerificationState.VERIFIED
    assert result.semantic_verification_performed is True
    assert result.semantic_verifier_provider == "f7-static"
    assert result.canonical_conclusion == "Debe abandonar el régimen."
    assert result.canonical_conclusion_mutated is False
    assert result.facts_mutated is False
    assert result.normative_refs_mutated is False
    assert result.ratio_mutated is False
    assert result.can_control_legal_decision is False


def test_f7_detects_h1_context_digest_tampering_as_correction_required() -> None:
    packet = _h1_packet()
    assert packet.h1_result is not None and packet.h1_result.hypothesis is not None
    tampered_hypothesis = packet.h1_result.hypothesis.model_copy(
        update={"source_context_sha256": "f" * 64}
    )
    tampered_h1 = packet.h1_result.model_copy(update={"hypothesis": tampered_hypothesis})
    tampered = packet.model_copy(update={"h1_result": tampered_h1})

    result = verify_hybrid_legal_argument(tampered)

    assert result.state is HybridLegalVerificationState.CORRECTION_REQUIRED
    assert "h1_context_digest_mismatch" in result.correction_codes
    assert result.h1_context_integrity_verified is False


def test_f7_detects_h1_fact_boundary_violation_even_if_object_is_tampered_post_validation() -> None:
    packet = _h1_packet()
    assert packet.h1_result is not None and packet.h1_result.hypothesis is not None
    fact = packet.h1_result.hypothesis.facts_used[0].model_copy(
        update={"name": "invented_income", "value": "5000000"}
    )
    hypothesis = packet.h1_result.hypothesis.model_copy(update={"facts_used": [fact]})
    tampered = packet.model_copy(
        update={"h1_result": packet.h1_result.model_copy(update={"hypothesis": hypothesis})}
    )

    result = verify_hybrid_legal_argument(tampered)

    assert result.state is HybridLegalVerificationState.CORRECTION_REQUIRED
    assert "h1_fact_boundary_violation" in result.correction_codes
    assert result.h1_fact_boundary_verified is False


def test_f7_detects_missing_rbs_or_cbr_contrast_for_generated_h1() -> None:
    packet = _h1_packet()
    tampered = packet.model_copy(update={"rbs_h1_contrast": None, "cbr_h1_contrast": None})

    result = verify_hybrid_legal_argument(tampered)

    assert result.state is HybridLegalVerificationState.CORRECTION_REQUIRED
    assert "h1_missing_rbs_contrast" in result.correction_codes
    assert "h1_missing_cbr_contrast" in result.correction_codes


def test_f7_rejects_cbr_promotion_to_normative_authority() -> None:
    packet = _h1_packet()
    assert packet.cbr_h1_contrast is not None
    promoted = packet.cbr_h1_contrast.model_copy(
        update={"cbr_is_normative_authority": True}
    )
    tampered = packet.model_copy(update={"cbr_h1_contrast": promoted})

    result = verify_hybrid_legal_argument(tampered)

    assert result.state is HybridLegalVerificationState.CORRECTION_REQUIRED
    assert "cbr_role_violation" in result.correction_codes
    assert result.cbr_experiential_role_preserved is False


def test_f7_revalidates_h2_against_justification_context_and_f6_link() -> None:
    packet = _binding_packet()
    draft = _semantic_draft(packet)

    result = verify_hybrid_legal_argument(packet, semantic_draft=draft)

    assert result.state is HybridLegalVerificationState.VERIFIED
    assert result.h2_source_fidelity_verified is True
    assert result.h2_normative_boundary_verified is True
    assert result.binding_jurisprudence_respected is True
    assert result.h2_ratio_ids


def test_f7_h2_context_digest_mismatch_requires_correction() -> None:
    packet = _binding_packet()
    original = packet.h2_results[0]
    assert original.ratio is not None
    ratio = original.ratio.model_copy(update={"source_context_sha256": "e" * 64})
    tampered = packet.model_copy(
        update={"h2_results": [original.model_copy(update={"ratio": ratio})]}
    )

    result = verify_hybrid_legal_argument(tampered)

    assert result.state is HybridLegalVerificationState.CORRECTION_REQUIRED
    assert any(code.startswith("h2_source_fidelity_violation:") for code in result.correction_codes)
    assert result.h2_source_fidelity_verified is False


def test_f7_detects_binding_jurisprudence_lost_by_f6() -> None:
    packet = _binding_packet()
    assert packet.coordination is not None
    coordination = packet.coordination.model_copy(
        update={
            "binding_interpretation_required": False,
            "binding_jurisprudence_document_ids": [],
            "binding_jurisprudence_evidence_refs": [],
        }
    )
    tampered = packet.model_copy(update={"coordination": coordination})

    result = verify_hybrid_legal_argument(tampered)

    assert result.state is HybridLegalVerificationState.CORRECTION_REQUIRED
    assert "binding_jurisprudence_not_preserved" in result.correction_codes
    assert result.binding_jurisprudence_respected is False


def test_f7_semantic_packet_digest_mismatch_requires_correction() -> None:
    packet = _h1_packet()
    draft = _semantic_draft(packet, packet_sha256="f" * 64)

    result = verify_hybrid_legal_argument(packet, semantic_draft=draft)

    assert result.state is HybridLegalVerificationState.CORRECTION_REQUIRED
    assert "semantic_packet_digest_mismatch" in result.correction_codes


def test_f7_semantic_unresolved_routes_to_human_review_without_redecision() -> None:
    packet = _h1_packet()
    draft = _semantic_draft(
        packet,
        h1_consistency=HybridSemanticAssessment.UNRESOLVED.value,
    )

    result = verify_hybrid_legal_argument(packet, semantic_draft=draft)

    assert result.state is HybridLegalVerificationState.HUMAN_REVIEW
    assert "semantic_consistency_unresolved" in result.review_codes
    assert result.canonical_conclusion == "Debe abandonar el régimen."
    assert result.canonical_conclusion_mutated is False


def test_f7_semantic_inconsistency_requires_correction_but_does_not_modify_sources() -> None:
    packet = _h1_packet()
    draft = _semantic_draft(
        packet,
        rbs_representation=HybridSemanticAssessment.INCONSISTENT.value,
    )

    result = verify_hybrid_legal_argument(packet, semantic_draft=draft)

    assert result.state is HybridLegalVerificationState.CORRECTION_REQUIRED
    assert "semantic_inconsistency_detected" in result.correction_codes
    assert result.rbs_reexecuted is False
    assert result.cbr_reexecuted is False
    assert result.e6_application_recomputed is False


def test_f7_llama_verifier_prompt_forbids_external_sources_and_redecision() -> None:
    packet = _h1_packet()
    provider = StaticVerificationProvider(_semantic_payload(packet))

    draft = LlamaHybridLegalVerificationService(provider).generate(packet)

    assert draft.packet_sha256 == hybrid_verification_packet_sha256(packet)
    assert provider.messages is not None
    system = provider.messages[0]["content"]
    user = provider.messages[1]["content"]
    system_lower = " ".join(system.lower().split())
    assert "no modifiques la conclusión canónica" in system_lower
    assert "no inventes hechos, normas, jurisprudencia" in system_lower
    assert '"external_sources_allowed":false' in user
    assert '"may_change_canonical_conclusion":false' in user
    assert '"cbr_is_experiential_only":true' in user


def test_f7_result_channel_is_additive_and_not_runtime_activated() -> None:
    baseline = _orchestrator(None).run(_request())

    assert "hybrid_legal_verification" in HybridOrchestrationResult.model_fields
    assert baseline.hybrid_legal_verification is None
    assert baseline.hybrid_legal_coordination is None
    assert baseline.llama_fiscal_hypothesis_h1 is None


def test_f7_verification_object_does_not_change_analyzer_or_legal_decision() -> None:
    baseline = _orchestrator(None).run(_request())
    coordination = coordinate_hybrid_legal_argument(
        applicable_normative_refs=list(baseline.applicable_normative_refs),
        existing_coordination=baseline.hybrid_coordination,
    )
    packet = build_hybrid_legal_verification_packet(coordination=coordination)
    verification = verify_hybrid_legal_argument(packet)
    enriched = baseline.model_copy(
        update={
            "hybrid_legal_coordination": coordination,
            "hybrid_legal_verification": verification,
        }
    )

    baseline_analysis = build_integral_legal_analysis(baseline)
    enriched_analysis = build_integral_legal_analysis(enriched)
    baseline_decision = build_legal_decision(baseline_analysis)
    enriched_decision = build_legal_decision(enriched_analysis)

    assert enriched_analysis == baseline_analysis
    assert enriched_decision == baseline_decision


def test_f7_preserves_f1_contracts_and_real_llm_remains_inactive() -> None:
    audit = audit_current_hybrid_contracts()

    assert audit.all_contracts_preserved is True
    assert audit.real_llm_activation_performed is False
    assert audit.h1_h2_runtime_activation_performed is False
    assert audit.runtime_order_changed is False
    assert audit.legal_decision_changed is False
