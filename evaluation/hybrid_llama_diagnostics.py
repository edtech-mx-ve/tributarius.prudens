from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.domain.hybrid_legal_verification import (
    HybridLegalSemanticVerificationDraft,
    HybridLegalVerificationPacket,
)
from app.domain.hybrid_llama_hypotheses import (
    FiscalHypothesisH1Draft,
    JurisprudentialRatioH2Draft,
)
from app.domain.hybrid_llama_runtime import HybridLlamaRuntimeResult
from app.domain.llama_hybrid_context import (
    InitialFiscalHypothesisContext,
    JurisprudentialRatioContext,
)
from app.services.hybrid_hypothesis_control import (
    HybridHypothesisValidationError,
    validate_fiscal_hypothesis_h1,
    validate_jurisprudential_ratio_h2,
)
from app.services.hybrid_legal_verification import (
    build_hybrid_legal_verification_packet,
    hybrid_verification_packet_sha256,
    validate_semantic_verification_draft,
)
from llm.hybrid_compact_contracts import (
    CompactContractError,
    CompactFiscalHypothesisH1Draft,
    CompactHybridLegalSemanticVerificationDraft,
    CompactJurisprudentialRatioH2Draft,
    expand_compact_h1,
    expand_compact_h2,
    expand_compact_verification,
)
from llm.models import LLMGenerationContext


class DiagnosticProvider(Protocol):
    @property
    def provider_name(self) -> str: ...

    @property
    def model_name(self) -> str: ...

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str: ...

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str: ...


class F12DiagnosticValidationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str
    issue_type: str
    message: str


class F12DiagnosticCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    call_index: int = Field(ge=0)
    stage: str = Field(min_length=1, max_length=80)
    schema_title: str | None = Field(default=None, max_length=200)
    provider_name: str = Field(min_length=1, max_length=100)
    model_name: str = Field(min_length=1, max_length=200)
    prompt_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    prompt_characters: int = Field(ge=0)
    response_schema_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    duration_seconds: float = Field(ge=0.0)
    raw_response: str | None = None
    raw_response_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    provider_error_type: str | None = Field(default=None, max_length=200)
    provider_error_message: str | None = Field(default=None, max_length=4000)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    finish_reason: str | None = Field(default=None, max_length=100)


class F12StageDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: str
    context_ref: str
    call_index: int | None = Field(default=None, ge=0)
    accepted: bool = False
    transport: str = Field(default="none", pattern=r"^(none|canonical|compact)$")
    failure_class: str = Field(
        default="none",
        pattern=r"^(none|provider_generation|json_validation|compact_expansion|legal_control)$",
    )
    canonical_validation_issues: list[F12DiagnosticValidationIssue] = Field(
        default_factory=list,
        max_length=100,
    )
    compact_validation_issues: list[F12DiagnosticValidationIssue] = Field(
        default_factory=list,
        max_length=100,
    )
    expansion_error: str | None = Field(default=None, max_length=4000)
    control_error: str | None = Field(default=None, max_length=4000)
    raw_response_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class F12ScenarioDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    runtime_status: str
    decision_status: str
    conclusion: str | None = None
    llm_failure_codes: list[str] = Field(default_factory=list, max_length=40)

    orchestration_requires_human_review: bool = False
    orchestration_review_sources: list[str] = Field(default_factory=list, max_length=40)
    verification_state: str | None = None
    verification_canonical_conclusion: str | None = None
    verification_review_codes: list[str] = Field(default_factory=list, max_length=40)
    verification_correction_codes: list[str] = Field(default_factory=list, max_length=40)

    semantic_h1_consistency: str | None = None
    semantic_rbs_representation: str | None = None
    semantic_cbr_role: str | None = None
    semantic_binding_jurisprudence_consistency: str | None = None
    semantic_h2_assessment_count: int = Field(default=0, ge=0)
    semantic_requires_human_review: bool | None = None
    semantic_contradiction_codes: list[str] = Field(default_factory=list, max_length=20)
    semantic_hallucination_signals: list[str] = Field(default_factory=list, max_length=20)

    rbs_h1_relation: str | None = None
    h1_disposition: str | None = None

    analysis_status: str | None = None
    analysis_canonical_conclusion: str | None = None
    analysis_requires_human_review: bool = False
    readiness_requires_human_review: bool = False
    readiness_missing_requirements: list[str] = Field(default_factory=list, max_length=100)

    decision_requires_human_review: bool = False
    decision_source_canonical_conclusion: str | None = None

    calls: list[F12DiagnosticCall] = Field(default_factory=list, max_length=40)
    stages: list[F12StageDiagnostic] = Field(default_factory=list, max_length=20)


class F12RealLlamaDiagnosticReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    report_id: str = "BLOCK_F12_1_REAL_LLAMA_DIAGNOSTICS_2026"
    provider_name: str
    model_name: str
    scenarios: list[F12ScenarioDiagnostic] = Field(min_length=1, max_length=20)
    diagnostic_only: bool = True
    changes_legal_result: bool = False
    raw_llm_output_persisted: bool = True
    prompt_text_persisted: bool = False


_STAGE_BY_SCHEMA_TITLE = {
    "CompactFiscalHypothesisH1Draft": "h1",
    "CompactJurisprudentialRatioH2Draft": "h2",
    "CompactHybridLegalSemanticVerificationDraft": "semantic_verification",
    "CompactRAGExplanationDraft": "rag_explanation",
}


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _validation_issues(exc: ValidationError) -> list[F12DiagnosticValidationIssue]:
    issues: list[F12DiagnosticValidationIssue] = []
    for item in exc.errors(include_url=False, include_context=False, include_input=False):
        location = ".".join(str(part) for part in item.get("loc", ())) or "<root>"
        issues.append(
            F12DiagnosticValidationIssue(
                location=location,
                issue_type=str(item.get("type", "validation_error")),
                message=str(item.get("msg", "validation error")),
            )
        )
    return issues


def _provider_usage(provider: object) -> dict[str, object]:
    raw = getattr(provider, "last_generation_usage", None)
    if not isinstance(raw, dict):
        return {}
    usage: dict[str, object] = {}
    for key in ("prompt_tokens", "completion_tokens", "total_tokens", "finish_reason"):
        value = raw.get(key)
        if isinstance(value, (int, str)) or value is None:
            usage[key] = value
    return usage


class F12DiagnosticStructuredProvider:
    """Observa llamadas LLM F.12 sin alterar mensajes, esquema ni salida."""

    def __init__(self, provider: DiagnosticProvider) -> None:
        self._provider = provider
        self._calls: list[F12DiagnosticCall] = []

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    @property
    def calls(self) -> tuple[F12DiagnosticCall, ...]:
        return tuple(self._calls)

    def mark(self) -> int:
        return len(self._calls)

    def calls_since(self, mark: int) -> list[F12DiagnosticCall]:
        return list(self._calls[mark:])

    def _record(
        self,
        *,
        stage: str,
        schema_title: str | None,
        prompt_payload: object,
        response_schema: dict[str, object],
        started: float,
        raw_response: str | None,
        error: Exception | None,
    ) -> None:
        usage = _provider_usage(self._provider)
        raw_sha = (
            hashlib.sha256(raw_response.encode("utf-8")).hexdigest()
            if raw_response is not None
            else None
        )
        prompt_serialized = json.dumps(
            prompt_payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        self._calls.append(
            F12DiagnosticCall(
                call_index=len(self._calls),
                stage=stage,
                schema_title=schema_title,
                provider_name=self.provider_name,
                model_name=self.model_name,
                prompt_sha256=hashlib.sha256(prompt_serialized.encode("utf-8")).hexdigest(),
                prompt_characters=len(prompt_serialized),
                response_schema_sha256=_canonical_json_sha256(response_schema),
                duration_seconds=time.perf_counter() - started,
                raw_response=raw_response,
                raw_response_sha256=raw_sha,
                provider_error_type=type(error).__name__ if error is not None else None,
                provider_error_message=str(error) if error is not None else None,
                prompt_tokens=_optional_int(usage.get("prompt_tokens")),
                completion_tokens=_optional_int(usage.get("completion_tokens")),
                total_tokens=_optional_int(usage.get("total_tokens")),
                finish_reason=(
                    str(usage["finish_reason"])
                    if usage.get("finish_reason") is not None
                    else None
                ),
            )
        )

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        schema_title = (
            str(response_schema.get("title"))
            if response_schema.get("title") is not None
            else None
        )
        stage = _STAGE_BY_SCHEMA_TITLE.get(schema_title or "", "structured_other")
        started = time.perf_counter()
        try:
            raw = self._provider.generate_messages_json(
                messages,
                response_schema=response_schema,
            )
        except Exception as exc:
            self._record(
                stage=stage,
                schema_title=schema_title,
                prompt_payload=messages,
                response_schema=response_schema,
                started=started,
                raw_response=None,
                error=exc,
            )
            raise
        self._record(
            stage=stage,
            schema_title=schema_title,
            prompt_payload=messages,
            response_schema=response_schema,
            started=started,
            raw_response=raw,
            error=None,
        )
        return raw

    def generate_json(
        self,
        context: LLMGenerationContext,
        *,
        response_schema: dict[str, object],
    ) -> str:
        started = time.perf_counter()
        try:
            raw = self._provider.generate_json(context, response_schema=response_schema)
        except Exception as exc:
            self._record(
                stage="rag_explanation",
                schema_title=str(response_schema.get("title") or "") or None,
                prompt_payload=context.model_dump(mode="json"),
                response_schema=response_schema,
                started=started,
                raw_response=None,
                error=exc,
            )
            raise
        self._record(
            stage="rag_explanation",
            schema_title=str(response_schema.get("title") or "") or None,
            prompt_payload=context.model_dump(mode="json"),
            response_schema=response_schema,
            started=started,
            raw_response=raw,
            error=None,
        )
        return raw


def _provider_failure(
    stage: str,
    context_ref: str,
    call: F12DiagnosticCall | None,
) -> F12StageDiagnostic:
    return F12StageDiagnostic(
        stage=stage,
        context_ref=context_ref,
        call_index=call.call_index if call is not None else None,
        accepted=False,
        failure_class="provider_generation",
        control_error=(
            f"{call.provider_error_type}: {call.provider_error_message}"
            if call is not None and call.provider_error_type is not None
            else "No se observó una respuesta LLM para esta etapa."
        ),
        raw_response_sha256=call.raw_response_sha256 if call is not None else None,
    )


def diagnose_h1_call(
    call: F12DiagnosticCall | None,
    *,
    context: InitialFiscalHypothesisContext | None,
    provider_name: str,
    model_name: str,
) -> F12StageDiagnostic:
    context_ref = _canonical_json_sha256(context.model_dump(mode="json")) if context else "missing"
    if call is None or call.raw_response is None or context is None:
        return _provider_failure("h1", context_ref, call)

    raw = call.raw_response
    canonical_issues: list[F12DiagnosticValidationIssue] = []
    compact_issues: list[F12DiagnosticValidationIssue] = []
    try:
        draft = FiscalHypothesisH1Draft.model_validate_json(raw)
        transport = "canonical"
    except ValidationError as canonical_exc:
        canonical_issues = _validation_issues(canonical_exc)
        try:
            compact = CompactFiscalHypothesisH1Draft.model_validate_json(raw)
        except ValidationError as compact_exc:
            return F12StageDiagnostic(
                stage="h1",
                context_ref=context_ref,
                call_index=call.call_index,
                failure_class="json_validation",
                canonical_validation_issues=canonical_issues,
                compact_validation_issues=_validation_issues(compact_exc),
                raw_response_sha256=call.raw_response_sha256,
            )
        try:
            draft = expand_compact_h1(compact, context=context)
        except CompactContractError as exc:
            return F12StageDiagnostic(
                stage="h1",
                context_ref=context_ref,
                call_index=call.call_index,
                failure_class="compact_expansion",
                transport="compact",
                canonical_validation_issues=canonical_issues,
                compact_validation_issues=compact_issues,
                expansion_error=str(exc),
                raw_response_sha256=call.raw_response_sha256,
            )
        transport = "compact"

    try:
        validate_fiscal_hypothesis_h1(
            draft,
            context=context,
            provider_name=provider_name,
            model_name=model_name,
        )
    except HybridHypothesisValidationError as exc:
        return F12StageDiagnostic(
            stage="h1",
            context_ref=context_ref,
            call_index=call.call_index,
            accepted=False,
            transport=transport,
            failure_class="legal_control",
            canonical_validation_issues=canonical_issues,
            compact_validation_issues=compact_issues,
            control_error=str(exc),
            raw_response_sha256=call.raw_response_sha256,
        )
    return F12StageDiagnostic(
        stage="h1",
        context_ref=context_ref,
        call_index=call.call_index,
        accepted=True,
        transport=transport,
        raw_response_sha256=call.raw_response_sha256,
        canonical_validation_issues=canonical_issues,
    )


def diagnose_h2_call(
    call: F12DiagnosticCall | None,
    *,
    context: JurisprudentialRatioContext | None,
    provider_name: str,
    model_name: str,
) -> F12StageDiagnostic:
    context_ref = context.document_id if context is not None else "missing"
    if call is None or call.raw_response is None or context is None:
        return _provider_failure("h2", context_ref, call)

    raw = call.raw_response
    canonical_issues: list[F12DiagnosticValidationIssue] = []
    try:
        draft = JurisprudentialRatioH2Draft.model_validate_json(raw)
        transport = "canonical"
    except ValidationError as canonical_exc:
        canonical_issues = _validation_issues(canonical_exc)
        try:
            compact = CompactJurisprudentialRatioH2Draft.model_validate_json(raw)
        except ValidationError as compact_exc:
            return F12StageDiagnostic(
                stage="h2",
                context_ref=context_ref,
                call_index=call.call_index,
                failure_class="json_validation",
                canonical_validation_issues=canonical_issues,
                compact_validation_issues=_validation_issues(compact_exc),
                raw_response_sha256=call.raw_response_sha256,
            )
        try:
            draft = expand_compact_h2(compact, context=context)
        except CompactContractError as exc:
            return F12StageDiagnostic(
                stage="h2",
                context_ref=context_ref,
                call_index=call.call_index,
                transport="compact",
                failure_class="compact_expansion",
                canonical_validation_issues=canonical_issues,
                expansion_error=str(exc),
                raw_response_sha256=call.raw_response_sha256,
            )
        transport = "compact"

    try:
        validate_jurisprudential_ratio_h2(
            draft,
            context=context,
            provider_name=provider_name,
            model_name=model_name,
        )
    except HybridHypothesisValidationError as exc:
        return F12StageDiagnostic(
            stage="h2",
            context_ref=context_ref,
            call_index=call.call_index,
            transport=transport,
            failure_class="legal_control",
            canonical_validation_issues=canonical_issues,
            control_error=str(exc),
            raw_response_sha256=call.raw_response_sha256,
        )
    return F12StageDiagnostic(
        stage="h2",
        context_ref=context_ref,
        call_index=call.call_index,
        accepted=True,
        transport=transport,
        canonical_validation_issues=canonical_issues,
        raw_response_sha256=call.raw_response_sha256,
    )


def _verification_packet(result: HybridLlamaRuntimeResult) -> HybridLegalVerificationPacket | None:
    orchestration = result.orchestration
    coordination = orchestration.hybrid_legal_coordination
    if coordination is None:
        return None
    jurisprudence_application = None
    if orchestration.session_jurisprudence_result is not None:
        jurisprudence_application = orchestration.session_jurisprudence_result.decision_application
    return build_hybrid_legal_verification_packet(
        coordination=coordination,
        initial_context=orchestration.llama_initial_context,
        h1_result=orchestration.llama_fiscal_hypothesis_h1,
        rbs_h1_contrast=orchestration.rbs_h1_contrast,
        cbr_h1_contrast=orchestration.cbr_h1_contrast,
        h2_results=list(orchestration.llama_jurisprudential_ratio_h2),
        jurisprudence_ratio_contexts=list(orchestration.llama_jurisprudence_ratio_contexts),
        jurisprudence_application=jurisprudence_application,
        post_deterministic_context=orchestration.llama_hybrid_review_context,
    )


def diagnose_verification_call(
    call: F12DiagnosticCall | None,
    *,
    result: HybridLlamaRuntimeResult,
) -> F12StageDiagnostic:
    packet = _verification_packet(result)
    context_ref = hybrid_verification_packet_sha256(packet) if packet is not None else "missing"
    if call is None or call.raw_response is None or packet is None:
        return _provider_failure("semantic_verification", context_ref, call)

    raw = call.raw_response
    canonical_issues: list[F12DiagnosticValidationIssue] = []
    try:
        draft = HybridLegalSemanticVerificationDraft.model_validate_json(raw)
        transport = "canonical"
    except ValidationError as canonical_exc:
        canonical_issues = _validation_issues(canonical_exc)
        try:
            compact = CompactHybridLegalSemanticVerificationDraft.model_validate_json(raw)
        except ValidationError as compact_exc:
            return F12StageDiagnostic(
                stage="semantic_verification",
                context_ref=context_ref,
                call_index=call.call_index,
                failure_class="json_validation",
                canonical_validation_issues=canonical_issues,
                compact_validation_issues=_validation_issues(compact_exc),
                raw_response_sha256=call.raw_response_sha256,
            )
        try:
            draft = expand_compact_verification(
                compact,
                packet=packet,
                packet_sha256=context_ref,
            )
        except CompactContractError as exc:
            return F12StageDiagnostic(
                stage="semantic_verification",
                context_ref=context_ref,
                call_index=call.call_index,
                transport="compact",
                failure_class="compact_expansion",
                canonical_validation_issues=canonical_issues,
                expansion_error=str(exc),
                raw_response_sha256=call.raw_response_sha256,
            )
        transport = "compact"

    failures = validate_semantic_verification_draft(packet, draft)
    if failures:
        return F12StageDiagnostic(
            stage="semantic_verification",
            context_ref=context_ref,
            call_index=call.call_index,
            transport=transport,
            failure_class="legal_control",
            canonical_validation_issues=canonical_issues,
            control_error=", ".join(failures),
            raw_response_sha256=call.raw_response_sha256,
        )
    return F12StageDiagnostic(
        stage="semantic_verification",
        context_ref=context_ref,
        call_index=call.call_index,
        accepted=True,
        transport=transport,
        canonical_validation_issues=canonical_issues,
        raw_response_sha256=call.raw_response_sha256,
    )


def diagnose_scenario(
    *,
    scenario_id: str,
    result: HybridLlamaRuntimeResult,
    calls: list[F12DiagnosticCall],
) -> F12ScenarioDiagnostic:
    by_stage: dict[str, list[F12DiagnosticCall]] = {}
    for call in calls:
        by_stage.setdefault(call.stage, []).append(call)

    stages: list[F12StageDiagnostic] = []
    h1_calls = by_stage.get("h1", [])
    h1_call: F12DiagnosticCall | None = h1_calls[0] if h1_calls else None
    stages.append(
        diagnose_h1_call(
            h1_call,
            context=result.orchestration.llama_initial_context,
            provider_name=result.provider_name,
            model_name=result.model_name,
        )
    )

    h2_calls = by_stage.get("h2", [])
    contexts = list(result.orchestration.llama_jurisprudence_ratio_contexts)
    for index, context in enumerate(contexts):
        h2_call: F12DiagnosticCall | None = (
            h2_calls[index] if index < len(h2_calls) else None
        )
        stages.append(
            diagnose_h2_call(
                h2_call,
                context=context,
                provider_name=result.provider_name,
                model_name=result.model_name,
            )
        )

    verification_calls = by_stage.get("semantic_verification", [])
    if result.semantic_verification_attempted:
        stages.append(
            diagnose_verification_call(
                verification_calls[0] if verification_calls else None,
                result=result,
            )
        )

    verification = result.orchestration.hybrid_legal_verification
    semantic = verification.semantic_draft if verification is not None else None
    coordination = result.orchestration.hybrid_legal_coordination

    orchestration = result.orchestration
    review_sources: list[str] = []
    if orchestration.analysis.requires_human_review:
        review_sources.append("analysis")
    if any(item.requires_human_review for item in orchestration.normative_results):
        review_sources.append("normative_results")
    if (
        orchestration.temporal_control_execution is not None
        and orchestration.temporal_control_execution.requires_human_review
    ):
        review_sources.append("temporal_control")
    if orchestration.rule_result.requires_human_review:
        review_sources.append("rbs")
    if (
        orchestration.isr_trace_verification is not None
        and not orchestration.isr_trace_verification.verified
    ):
        review_sources.append("isr_trace_verification")
    if any(item.requires_human_review for item in orchestration.cbr_reuse_assessments):
        review_sources.append("cbr_reuse")
    if (
        orchestration.hybrid_coordination is not None
        and orchestration.hybrid_coordination.requires_review
    ):
        review_sources.append("rbs_cbr_coordination")
    if (
        orchestration.heuristic_evaluation is not None
        and orchestration.heuristic_evaluation.requires_review
    ):
        review_sources.append("heuristic_evaluation")
    if (
        orchestration.session_jurisprudence_result is not None
        and orchestration.session_jurisprudence_result.requires_human_review
    ):
        review_sources.append("session_jurisprudence")
    if (
        orchestration.explanation is not None
        and orchestration.explanation.answer.requires_human_review
    ):
        review_sources.append("llm_explanation")
    if (
        orchestration.llama_fiscal_hypothesis_h1 is not None
        and orchestration.llama_fiscal_hypothesis_h1.requires_human_review
    ):
        review_sources.append("h1_generation")
    if (
        orchestration.rbs_h1_contrast is not None
        and orchestration.rbs_h1_contrast.requires_human_review
    ):
        review_sources.append("rbs_h1_contrast")
    if (
        orchestration.cbr_h1_contrast is not None
        and orchestration.cbr_h1_contrast.requires_human_review
    ):
        review_sources.append("cbr_h1_contrast")

    return F12ScenarioDiagnostic(
        scenario_id=scenario_id,
        runtime_status=result.status.value,
        decision_status=result.decision.status.value,
        conclusion=result.decision.conclusion,
        llm_failure_codes=list(result.llm_failure_codes),
        orchestration_requires_human_review=result.orchestration.requires_human_review,
        orchestration_review_sources=review_sources,
        verification_state=(verification.state.value if verification is not None else None),
        verification_canonical_conclusion=(
            verification.canonical_conclusion if verification is not None else None
        ),
        verification_review_codes=(
            list(verification.review_codes) if verification is not None else []
        ),
        verification_correction_codes=(
            list(verification.correction_codes) if verification is not None else []
        ),
        semantic_h1_consistency=(
            semantic.h1_consistency.value if semantic is not None else None
        ),
        semantic_rbs_representation=(
            semantic.rbs_representation.value if semantic is not None else None
        ),
        semantic_cbr_role=(semantic.cbr_role.value if semantic is not None else None),
        semantic_binding_jurisprudence_consistency=(
            semantic.binding_jurisprudence_consistency.value
            if semantic is not None
            else None
        ),
        semantic_h2_assessment_count=(
            len(semantic.h2_assessments) if semantic is not None else 0
        ),
        semantic_requires_human_review=(
            semantic.requires_human_review if semantic is not None else None
        ),
        semantic_contradiction_codes=(
            list(semantic.contradiction_codes) if semantic is not None else []
        ),
        semantic_hallucination_signals=(
            list(semantic.hallucination_signals) if semantic is not None else []
        ),
        rbs_h1_relation=(
            coordination.rbs_h1_relation.value
            if coordination is not None and coordination.rbs_h1_relation is not None
            else None
        ),
        h1_disposition=(
            coordination.h1_disposition.value if coordination is not None else None
        ),
        analysis_status=result.analysis.status.value,
        analysis_canonical_conclusion=result.analysis.canonical_conclusion,
        analysis_requires_human_review=result.analysis.requires_human_review,
        readiness_requires_human_review=result.analysis.readiness.requires_human_review,
        readiness_missing_requirements=list(result.analysis.readiness.missing_requirements),
        decision_requires_human_review=result.decision.requires_human_review,
        decision_source_canonical_conclusion=(
            result.decision.hybrid_projection.source_canonical_conclusion
        ),
        calls=calls,
        stages=stages,
    )


def export_f12_real_llama_diagnostic_report(
    report: F12RealLlamaDiagnosticReport,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return path
