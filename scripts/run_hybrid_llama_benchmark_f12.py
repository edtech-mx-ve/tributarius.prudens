from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.services.real_llama_runtime import RealLlamaRuntimeError, build_real_llama_provider
from evaluation.hybrid_llama_benchmark import (
    HybridLlamaBenchmarkError,
    export_hybrid_llama_benchmark_report,
    run_hybrid_llama_benchmark,
)
from evaluation.hybrid_llama_fixtures import F12ReferenceStructuredProvider

_DEFAULT_OUTPUT = Path("evaluation/reports/block_f12_hybrid_llama_benchmark.json")


def main() -> int:
    settings = get_settings()
    try:
        real_provider, descriptor = build_real_llama_provider(settings)
        report = run_hybrid_llama_benchmark(
            reference_provider=F12ReferenceStructuredProvider(),
            real_provider=real_provider,
        )
        output = export_hybrid_llama_benchmark_report(report, _DEFAULT_OUTPUT)
    except (RealLlamaRuntimeError, HybridLlamaBenchmarkError) as exc:
        print(f"ERROR: benchmark F.12 rechazado: {exc}")
        return 1

    print("F.12 benchmark híbrido: baseline determinista de prueba vs Llama real")
    print(f"- provider={descriptor.provider_name}")
    print(f"- model={descriptor.model_name}")
    print(f"- model_sha256={descriptor.model_sha256}")
    print(f"- report={output}")
    print(f"- conclusion_stability={report.conclusion_stability:.3f}")
    print(f"- hallucination_rate={report.hallucination_rate:.3f}")
    print(f"- safety_passed={str(report.safety_passed).lower()}")
    print(f"- quality_passed={str(report.quality_passed).lower()}")
    print(f"- overall_passed={str(report.overall_passed).lower()}")
    for case in report.real_llama.cases:
        print(
            "- real_case="
            f"{case.scenario_id}; passed={str(case.passed).lower()}; "
            f"status={case.decision_status}; duration={case.duration_seconds:.3f}s"
        )
        if case.failures:
            print("  failures=" + "; ".join(case.failures))
        if case.llm_failure_codes:
            print("  llm_failure_codes=" + ",".join(case.llm_failure_codes))
    return 0 if report.overall_passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
