from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.services.real_llama_runtime import RealLlamaRuntimeError, build_real_llama_provider
from evaluation.hybrid_llama_benchmark import (
    HybridLlamaBenchmarkError,
    load_hybrid_llama_benchmark_suite,
)
from evaluation.hybrid_llama_diagnostics import (
    F12DiagnosticStructuredProvider,
    F12RealLlamaDiagnosticReport,
    F12ScenarioDiagnostic,
    diagnose_scenario,
    export_f12_real_llama_diagnostic_report,
)
from evaluation.hybrid_llama_fixtures import build_f12_request, build_f12_runtime

_DEFAULT_OUTPUT = Path("evaluation/reports/block_f12_1_real_llama_diagnostics.json")


def main() -> int:
    settings = get_settings()
    try:
        real_provider, descriptor = build_real_llama_provider(settings)
        observed_provider = F12DiagnosticStructuredProvider(real_provider)
        runtime = build_f12_runtime(
            observed_provider,
            provider_is_test_double=False,
        )
        suite = load_hybrid_llama_benchmark_suite()

        scenarios: list[F12ScenarioDiagnostic] = []
        for suite_scenario in suite.scenarios:
            mark = observed_provider.mark()
            result = runtime.run(
                build_f12_request(
                    with_jurisprudence=suite_scenario.with_jurisprudence
                )
            )
            scenarios.append(
                diagnose_scenario(
                    scenario_id=suite_scenario.scenario_id,
                    result=result,
                    calls=observed_provider.calls_since(mark),
                )
            )

        report = F12RealLlamaDiagnosticReport(
            provider_name=descriptor.provider_name,
            model_name=descriptor.model_name,
            scenarios=scenarios,
        )
        output = export_f12_real_llama_diagnostic_report(report, _DEFAULT_OUTPUT)
    except (RealLlamaRuntimeError, HybridLlamaBenchmarkError) as exc:
        print(f"ERROR: diagnóstico F.12.1 rechazado: {exc}")
        return 1

    print("F.12.1 diagnóstico real de H1/H2/verificador")
    print(f"- provider={descriptor.provider_name}")
    print(f"- model={descriptor.model_name}")
    print(f"- report={output}")
    for diagnostic_scenario in report.scenarios:
        print(
            f"- scenario={diagnostic_scenario.scenario_id}; "
            f"runtime={diagnostic_scenario.runtime_status}; "
            f"decision={diagnostic_scenario.decision_status}; failures="
            + (",".join(diagnostic_scenario.llm_failure_codes) or "none")
        )
        for stage in diagnostic_scenario.stages:
            call = next(
                (
                    item
                    for item in diagnostic_scenario.calls
                    if item.call_index == stage.call_index
                ),
                None,
            )
            usage = "tokens=n/a"
            if call is not None and call.total_tokens is not None:
                usage = (
                    f"tokens={call.total_tokens} "
                    f"(prompt={call.prompt_tokens}, completion={call.completion_tokens})"
                )
            duration = (
                f"duration={call.duration_seconds:.3f}s"
                if call is not None
                else "duration=n/a"
            )
            print(
                f"  stage={stage.stage}; accepted={str(stage.accepted).lower()}; "
                f"transport={stage.transport}; failure_class={stage.failure_class}; "
                f"{duration}; {usage}"
            )
            if stage.canonical_validation_issues:
                print(
                    "    canonical="
                    + " | ".join(
                        f"{item.location}:{item.issue_type}:{item.message}"
                        for item in stage.canonical_validation_issues[:8]
                    )
                )
            if stage.compact_validation_issues:
                print(
                    "    compact="
                    + " | ".join(
                        f"{item.location}:{item.issue_type}:{item.message}"
                        for item in stage.compact_validation_issues[:8]
                    )
                )
            if stage.expansion_error:
                print(f"    expansion_error={stage.expansion_error}")
            if stage.control_error:
                print(f"    control_error={stage.control_error}")
            if call is not None and call.raw_response_sha256 is not None:
                print(f"    raw_sha256={call.raw_response_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
