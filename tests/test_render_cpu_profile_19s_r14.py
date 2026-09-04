from __future__ import annotations

from pathlib import Path

from scripts.validate_deployment import validate_render_blueprint


def test_render_blueprint_is_cpu_only_and_resource_bounded() -> None:
    checks = validate_render_blueprint(Path("render.yaml"))
    required = {
        "build-installs-cpu-torch",
        "build-validates-cpu-runtime",
        "rag-backend-lexical-cpu",
        "plan=1c-2g",
        "real-llama-provider",
        "real-llama-required",
        "build-bootstraps-real-llama",
        "omp-one-thread",
        "mkl-one-thread",
        "openblas-one-thread",
        "numexpr-one-thread",
    }
    assert required.issubset(set(checks))
