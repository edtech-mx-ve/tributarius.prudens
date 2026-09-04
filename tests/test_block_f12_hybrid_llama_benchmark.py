from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from evaluation.hybrid_llama_benchmark import (
    HybridLlamaBenchmarkError,
    export_hybrid_llama_benchmark_report,
    load_hybrid_llama_benchmark_suite,
    run_hybrid_llama_benchmark,
)
from evaluation.hybrid_llama_diagnostics import (
    F12DiagnosticStructuredProvider,
    diagnose_scenario,
)
from evaluation.hybrid_llama_fixtures import (
    F12ReferenceStructuredProvider,
    build_f12_request,
    build_f12_runtime,
)
from llm.hybrid_compact_contracts import (
    CompactFiscalHypothesisH1Draft,
    CompactHybridLegalSemanticVerificationDraft,
    CompactJurisprudentialRatioH2Draft,
)
from llm.providers.llama_cpp import LlamaCppProvider


class RealLikeReferenceProvider(F12ReferenceStructuredProvider):
    @property
    def provider_name(self) -> str:
        return "llama-cpp-python"

    @property
    def model_name(self) -> str:
        return "Llama-3.2-1B-Instruct-Q4_K_M"


class WrongProvider(F12ReferenceStructuredProvider):
    @property
    def provider_name(self) -> str:
        return "not-real-llama"


class FailingVerifierProvider(RealLikeReferenceProvider):
    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        import json

        payload = json.loads(messages[-1]["content"])
        if payload["task"] == "verificar_argumento_hibrido_sin_redecidir":
            from llm.errors import LLMGenerationError

            raise LLMGenerationError("fallo sintético del verificador")
        return super().generate_messages_json(
            messages,
            response_schema=response_schema,
        )


class HallucinatingVerifierProvider(RealLikeReferenceProvider):
    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        import json

        raw = super().generate_messages_json(messages, response_schema=response_schema)
        payload = json.loads(messages[-1]["content"])
        if payload["task"] != "verificar_argumento_hibrido_sin_redecidir":
            return raw
        response = json.loads(raw)
        response["hallucination_signals"] = ["invented_external_authority"]
        response["requires_human_review"] = True
        return json.dumps(response, ensure_ascii=False)


def test_f12_suite_covers_with_and_without_jurisprudence() -> None:
    suite = load_hybrid_llama_benchmark_suite()

    assert len(suite.scenarios) == 2
    assert {item.with_jurisprudence for item in suite.scenarios} == {False, True}
    assert any(item.expect_h2 for item in suite.scenarios)
    assert suite.thresholds.conclusion_stability == 1.0
    assert suite.thresholds.hallucination_rate_max == 0.0


def test_f12_reference_and_real_like_provider_pass_all_strict_gates() -> None:
    report = run_hybrid_llama_benchmark(
        reference_provider=F12ReferenceStructuredProvider(),
        real_provider=RealLikeReferenceProvider(),
    )

    assert report.reference.overall_passed is True
    assert report.real_llama.overall_passed is True
    assert report.conclusion_stability == 1.0
    assert report.hallucination_rate == 0.0
    assert report.safety_passed is True
    assert report.quality_passed is True
    assert report.overall_passed is True
    assert all(case.h1_generated for case in report.real_llama.cases)
    assert any(case.h2_generated for case in report.real_llama.cases)


def test_f12_real_provider_cannot_be_a_non_llama_provider() -> None:
    with pytest.raises(HybridLlamaBenchmarkError, match="llama-cpp-python"):
        run_hybrid_llama_benchmark(
            reference_provider=F12ReferenceStructuredProvider(),
            real_provider=WrongProvider(),
        )


def test_f12_hallucination_signal_fails_closed() -> None:
    report = run_hybrid_llama_benchmark(
        reference_provider=F12ReferenceStructuredProvider(),
        real_provider=HallucinatingVerifierProvider(),
    )

    assert report.hallucination_rate > 0.0
    assert report.safety_passed is False
    assert report.overall_passed is False


def test_f12_preserves_normative_authority_and_single_decision() -> None:
    report = run_hybrid_llama_benchmark(
        reference_provider=F12ReferenceStructuredProvider(),
        real_provider=RealLikeReferenceProvider(),
    )

    for case in report.real_llama.cases:
        assert case.metrics["legal_authority_integrity"] == 1.0
        assert case.metrics["single_decision_integrity"] == 1.0
        assert case.metrics["rbs_consistency"] == 1.0
        assert case.metrics["cbr_consistency"] == 1.0


def test_f12_jurisprudence_case_requires_traceable_h2() -> None:
    report = run_hybrid_llama_benchmark(
        reference_provider=F12ReferenceStructuredProvider(),
        real_provider=RealLikeReferenceProvider(),
    )
    case = next(
        item
        for item in report.real_llama.cases
        if item.scenario_id == "F12_WITH_JURISPRUDENCE"
    )

    assert case.h2_expected is True
    assert case.h2_generated is True
    assert case.metrics["ratio_fidelity"] == 1.0
    assert case.metrics["obiter_separation"] == 1.0
    assert case.metrics["jurisprudence_compliance"] == 1.0


def test_f12_without_jurisprudence_does_not_generate_h2() -> None:
    report = run_hybrid_llama_benchmark(
        reference_provider=F12ReferenceStructuredProvider(),
        real_provider=RealLikeReferenceProvider(),
    )
    case = next(
        item
        for item in report.real_llama.cases
        if item.scenario_id == "F12_WITHOUT_JURISPRUDENCE"
    )

    assert case.h2_expected is False
    assert case.h2_generated is False
    assert case.metrics["ratio_fidelity"] == 1.0


def test_f12_generation_failure_is_not_mislabeled_as_hallucination() -> None:
    report = run_hybrid_llama_benchmark(
        reference_provider=F12ReferenceStructuredProvider(),
        real_provider=FailingVerifierProvider(),
    )

    assert report.real_llama.overall_passed is False
    assert report.real_llama.aggregate_metrics["generation_success"] == 0.0
    assert report.hallucination_rate == 0.0


def test_f12_exports_traceable_json_report(tmp_path: Path) -> None:
    report = run_hybrid_llama_benchmark(
        reference_provider=F12ReferenceStructuredProvider(),
        real_provider=RealLikeReferenceProvider(),
    )
    output = export_hybrid_llama_benchmark_report(report, tmp_path / "report.json")

    assert output.is_file()
    text = output.read_text(encoding="utf-8")
    assert "BLOCK_F12_HYBRID_LLAMA_2026" in text
    assert "Llama-3.2-1B-Instruct-Q4_K_M" in text
    assert '"overall_passed": true' in text


def test_f12_runtime_script_requires_real_llama_builder_not_mock() -> None:
    source = Path("scripts/run_hybrid_llama_benchmark_f12.py").read_text(
        encoding="utf-8"
    )

    assert "build_real_llama_provider(settings)" in source
    assert "MockLLMProvider" not in source
    assert "F12ReferenceStructuredProvider" in source
    assert "overall_passed" in source


def test_f12_real_llama_sanitizes_bounded_schema_before_grammar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    model = tmp_path / "model.gguf"
    model.write_bytes(b"fixture")
    completion_kwargs: dict[str, object] = {}

    class FakeBackend:
        def create_chat_completion(self, **kwargs: object) -> object:
            completion_kwargs.update(kwargs)
            return {
                "choices": [
                    {
                        "message": {
                            "content": '{"name":"x","facts":[]}'
                        }
                    }
                ]
            }

    monkeypatch.setattr(
        "llm.providers.llama_cpp.importlib.import_module",
        lambda name: (
            SimpleNamespace(Llama=lambda **kwargs: FakeBackend())
            if name == "llama_cpp"
            else None
        ),
    )

    provider = LlamaCppProvider(
        model,
        n_ctx=2048,
        max_tokens=128,
        n_threads=1,
        n_batch=64,
    )
    provider.generate_messages_json(
        [{"role": "user", "content": "{}"}],
        response_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 4096,
                },
                "facts": {
                    "type": "array",
                    "maxItems": 100,
                    "items": {
                        "type": "string",
                        "maxLength": 2048,
                    },
                },
            },
            "required": ["name", "facts"],
            "additionalProperties": False,
        },
    )

    response_format = completion_kwargs["response_format"]
    assert isinstance(response_format, dict)
    grammar_schema = response_format["schema"]
    assert isinstance(grammar_schema, dict)

    rendered = repr(grammar_schema)
    assert "maxLength" not in rendered
    assert "minLength" not in rendered
    assert "maxItems" not in rendered
    assert grammar_schema["required"] == ["name", "facts"]
    assert grammar_schema["additionalProperties"] is False


class InvalidH1RealLikeProvider(RealLikeReferenceProvider):
    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        if response_schema.get("title") == "CompactFiscalHypothesisH1Draft":
            return '{"legal_problem":4}'
        return super().generate_messages_json(
            messages,
            response_schema=response_schema,
        )


def test_f12_1_diagnostic_captures_raw_h1_and_exact_validation_failure() -> None:
    provider = F12DiagnosticStructuredProvider(InvalidH1RealLikeProvider())
    runtime = build_f12_runtime(provider, provider_is_test_double=False)
    mark = provider.mark()

    result = runtime.run(build_f12_request(with_jurisprudence=False))
    diagnostic = diagnose_scenario(
        scenario_id="F12_WITHOUT_JURISPRUDENCE",
        result=result,
        calls=provider.calls_since(mark),
    )

    h1 = next(item for item in diagnostic.stages if item.stage == "h1")
    call = next(item for item in diagnostic.calls if item.call_index == h1.call_index)
    assert h1.accepted is False
    assert h1.failure_class == "json_validation"
    assert h1.compact_validation_issues
    assert call.raw_response == '{"legal_problem":4}'
    assert call.raw_response_sha256 is not None
    assert call.prompt_sha256 != call.raw_response_sha256


def test_f12_1_diagnostic_wrapper_identifies_h1_schema_without_mutation() -> None:
    provider = F12DiagnosticStructuredProvider(InvalidH1RealLikeProvider())
    messages = [
        {"role": "system", "content": "diagnostic fixture"},
        {"role": "user", "content": '{"task":"diagnostic_fixture"}'},
    ]
    schema = CompactFiscalHypothesisH1Draft.model_json_schema()

    raw = provider.generate_messages_json(messages, response_schema=schema)

    call = provider.calls[-1]
    assert call.stage == "h1"
    assert call.schema_title == "CompactFiscalHypothesisH1Draft"
    assert call.raw_response == raw
    assert call.provider_error_type is None
    assert call.duration_seconds >= 0.0


def test_f12_1_runtime_script_is_diagnostic_only_and_uses_real_llama() -> None:
    source = Path("scripts/run_hybrid_llama_diagnostics_f12_1.py").read_text(
        encoding="utf-8"
    )

    assert "build_real_llama_provider(settings)" in source
    assert "F12DiagnosticStructuredProvider" in source
    assert "MockLLMProvider" not in source
    assert "diagnose_scenario" in source


class OverAssessingBindingVerifierProvider(RealLikeReferenceProvider):
    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        import json

        raw = super().generate_messages_json(messages, response_schema=response_schema)
        payload = json.loads(messages[-1]["content"])
        if payload["task"] != "verificar_argumento_hibrido_sin_redecidir":
            return raw
        response = json.loads(raw)
        response["binding_jurisprudence_consistency"] = "consistent"
        return json.dumps(response, ensure_ascii=False)


def test_f12_2_compact_h1_h2_transport_removes_runaway_free_text_lists() -> None:
    h1_properties = CompactFiscalHypothesisH1Draft.model_json_schema()["properties"]
    h2_properties = CompactJurisprudentialRatioH2Draft.model_json_schema()["properties"]

    assert "candidate_normative_questions" not in h1_properties
    assert "assumptions" not in h1_properties
    assert "uncertainties" not in h1_properties
    assert "confidence_band" in h1_properties

    assert "essential_premises" not in h2_properties
    assert "possible_obiter" not in h2_properties
    assert "uncertainties" not in h2_properties
    assert "obiter_span_indices" in h2_properties
    assert "confidence_band" in h2_properties


def test_f12_2_verifier_normalizes_structural_non_applicability() -> None:
    provider = OverAssessingBindingVerifierProvider()
    runtime = build_f12_runtime(provider, provider_is_test_double=False)

    result = runtime.run(build_f12_request(with_jurisprudence=False))

    assert result.status.value == "completed"
    verification = result.orchestration.hybrid_legal_verification
    assert verification is not None
    assert verification.semantic_draft is not None
    assert verification.semantic_draft.binding_jurisprudence_consistency.value == (
        "not_applicable"
    )
    assert "semantic_verification_failed" not in result.llm_failure_codes


class SchemaCapturingProvider(RealLikeReferenceProvider):
    def __init__(self) -> None:
        self.schemas: dict[str, dict[str, object]] = {}

    def generate_messages_json(
        self,
        messages: list[dict[str, str]],
        *,
        response_schema: dict[str, object],
    ) -> str:
        import json

        task = json.loads(messages[-1]["content"])["task"]
        self.schemas[task] = response_schema
        return super().generate_messages_json(
            messages,
            response_schema=response_schema,
        )


def test_f12_3_dynamic_schema_restricts_h2_catalog_indices() -> None:
    provider = SchemaCapturingProvider()
    runtime = build_f12_runtime(provider, provider_is_test_double=False)

    result = runtime.run(build_f12_request(with_jurisprudence=True))

    assert result.status.value == "completed"
    schema = provider.schemas["formular_h2_ratio_decidendi_controlada"]
    properties = schema["properties"]
    assert isinstance(properties, dict)

    support = properties["support_span_indices"]
    assert isinstance(support, dict)
    support_items = support["items"]
    assert isinstance(support_items, dict)
    allowed_support = support_items["enum"]
    assert isinstance(allowed_support, list)
    assert allowed_support
    assert allowed_support == list(range(len(allowed_support)))

    normative = properties["normative_ref_indices"]
    assert isinstance(normative, dict)
    normative_items = normative["items"]
    assert isinstance(normative_items, dict)
    allowed_norms = normative_items["enum"]
    assert isinstance(allowed_norms, list)
    assert allowed_norms == list(range(len(allowed_norms)))


def test_f12_3_verifier_schema_requires_h1_assessment_when_h1_exists() -> None:
    provider = SchemaCapturingProvider()
    runtime = build_f12_runtime(provider, provider_is_test_double=False)

    result = runtime.run(build_f12_request(with_jurisprudence=False))

    assert result.status.value == "completed"
    schema = provider.schemas["verificar_argumento_hibrido_sin_redecidir"]
    properties = schema["properties"]
    assert isinstance(properties, dict)

    h1_schema = properties["h1_consistency"]
    assert isinstance(h1_schema, dict)
    assert h1_schema["enum"] == ["consistent", "inconsistent", "unresolved"]

    binding_schema = properties["binding_jurisprudence_consistency"]
    assert isinstance(binding_schema, dict)
    assert binding_schema["enum"] == ["not_applicable"]


def test_f12_4_h2_duplicate_indices_are_canonicalized_as_set_selection() -> None:
    compact = CompactJurisprudentialRatioH2Draft.model_validate(
        {
            "legal_question": "¿Cuál es la premisa indispensable?",
            "normative_ref_indices": [0, 0],
            "support_span_indices": [1, 1, 2],
            "proposed_ratio": "La ratio se apoya sólo en las premisas seleccionadas.",
            "obiter_span_indices": [],
            "confidence_band": "medium",
        }
    )

    assert compact.normative_ref_indices == [0]
    assert compact.support_span_indices == [1, 2]


def test_f12_4_verifier_compact_h2_assessments_are_ordered_without_ratio_index() -> None:
    schema = CompactHybridLegalSemanticVerificationDraft.model_json_schema()
    definition = schema["$defs"]["CompactH2SemanticAssessment"]
    assert isinstance(definition, dict)
    properties = definition["properties"]
    assert isinstance(properties, dict)
    assert "ratio_index" not in properties


def test_f12_5_verifier_schema_forbids_h2_assessments_when_no_h2_exists() -> None:
    provider = SchemaCapturingProvider()
    runtime = build_f12_runtime(provider, provider_is_test_double=False)

    result = runtime.run(build_f12_request(with_jurisprudence=False))

    assert result.status.value == "completed"
    schema = provider.schemas["verificar_argumento_hibrido_sin_redecidir"]
    properties = schema["properties"]
    assert isinstance(properties, dict)
    h2_schema = properties["h2_assessments"]
    assert isinstance(h2_schema, dict)
    assert h2_schema["properties"] == {}
    assert h2_schema["additionalProperties"] is False
    assert "required" not in h2_schema


def test_f12_5_verifier_schema_requires_one_key_for_one_generated_h2() -> None:
    provider = SchemaCapturingProvider()
    runtime = build_f12_runtime(provider, provider_is_test_double=False)

    result = runtime.run(build_f12_request(with_jurisprudence=True))

    assert result.status.value == "completed"
    schema = provider.schemas["verificar_argumento_hibrido_sin_redecidir"]
    properties = schema["properties"]
    assert isinstance(properties, dict)
    h2_schema = properties["h2_assessments"]
    assert isinstance(h2_schema, dict)
    assert h2_schema["required"] == ["0"]
    assert set(h2_schema["properties"]) == {"0"}
    assert h2_schema["additionalProperties"] is False
