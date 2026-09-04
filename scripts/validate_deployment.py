from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class DeploymentValidationError(RuntimeError):
    pass


def _env_items(service: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    raw_env = service.get("envVars", [])
    if not isinstance(raw_env, list):
        raise DeploymentValidationError("envVars debe ser una lista.")
    for item in raw_env:
        if not isinstance(item, dict):
            raise DeploymentValidationError("envVars contiene una entrada inválida.")
        key = item.get("key")
        if not isinstance(key, str) or not key.strip():
            raise DeploymentValidationError("envVars contiene una key inválida.")
        if key in result:
            raise DeploymentValidationError(f"envVar duplicada: {key}.")
        result[key] = item
    return result


def _env_value(items: dict[str, dict[str, Any]], key: str) -> str | None:
    item = items.get(key)
    if item is None:
        return None
    value = item.get("value")
    return value if isinstance(value, str) else None


def validate_render_blueprint(path: Path) -> list[str]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise DeploymentValidationError("render.yaml debe contener un objeto raíz.")
    services = payload.get("services")
    if not isinstance(services, list) or len(services) != 1:
        raise DeploymentValidationError("Se requiere exactamente un Web Service.")

    service = services[0]
    if not isinstance(service, dict):
        raise DeploymentValidationError("La definición del servicio es inválida.")
    build_command = str(service.get("buildCommand", ""))
    checks = {
        "type=web": service.get("type") == "web",
        "runtime=python": service.get("runtime") == "python",
        "plan=1c-2g": service.get("plan") == "1c-2g",
        "health=/health": service.get("healthCheckPath") == "/health",
        "start-binds-host": "0.0.0.0" in str(service.get("startCommand", "")),
        "start-uses-port": "$PORT" in str(service.get("startCommand", "")),
        "build-installs-cpu-torch": (
            'torch==2.13.0' in build_command
            and "download.pytorch.org/whl/cpu" in build_command
        ),
        "build-installs-llama-cpp-cpu-wheel": (
            'llama-cpp-python==0.3.35' in build_command
            and "abetlen.github.io/llama-cpp-python/whl/cpu" in build_command
            and "--only-binary=llama-cpp-python" in build_command
        ),
        "build-installs-package-with-llama": 'pip install -e ".[llama]"' in build_command,
        "build-validates-cpu-runtime": (
            "scripts.verify_cpu_runtime_19s_r14" in build_command
        ),
        "build-bootstraps-runtime": (
            "scripts.bootstrap_runtime_release_19i18c" in build_command
        ),
        "build-bootstraps-real-llama": (
            "scripts.bootstrap_llama_model_f11" in build_command
        ),
        "no-databases": "databases" not in payload,
        "no-disk": "disk" not in service and "diskPath" not in service,
    }
    env = _env_items(service)
    release_url_item = env.get("RUNTIME_RELEASE_URL", {})
    checks.update(
        {
            "environment=production": _env_value(env, "ENVIRONMENT") == "production",
            "deployment=render": _env_value(env, "DEPLOYMENT_PLATFORM") == "render",
            "stateless-profile": _env_value(env, "RUNTIME_PROFILE") == "stateless_free",
            "sqlite-is-ephemeral": (
                _env_value(env, "DATABASE_URL") or ""
            ).startswith("sqlite:////tmp/"),
            "docs-disabled": (
                _env_value(env, "ENABLE_DOCS") or ""
            ).lower() == "false",
            "semantic-v2-runtime": (
                _env_value(env, "RAG_ARTIFACT_DIR")
                == "deployment/runtime_artifacts_semantic_v2"
            ),
            "rag-required": (
                _env_value(env, "REQUIRE_RAG_ARTIFACTS") or ""
            ).lower() == "true",
            "rag-backend-lexical-cpu": (
                _env_value(env, "RAG_RUNTIME_BACKEND") == "lexical_cpu"
            ),
            "rag-local-only": (
                _env_value(env, "RAG_LOCAL_FILES_ONLY") or ""
            ).lower() == "true",
            "rag-integrity-required": (
                _env_value(env, "VERIFY_RAG_INTEGRITY") or ""
            ).lower() == "true",
            "temporal-registry-required": (
                _env_value(env, "REQUIRE_TEMPORAL_PROVENANCE_REGISTRY") or ""
            ).lower() == "true",
            "python-3.12": (_env_value(env, "PYTHON_VERSION") or "").startswith("3.12."),
            "real-llama-provider": _env_value(env, "LLM_RUNTIME_PROVIDER") == "llama_cpp",
            "real-llama-required": (
                _env_value(env, "REQUIRE_REAL_LLAMA") or ""
            ).lower() == "true",
            "llama-model-path-gguf": (
                _env_value(env, "LLAMA_MODEL_PATH") or ""
            ).endswith(".gguf"),
            "llama-model-url-https": (
                _env_value(env, "LLAMA_MODEL_URL") or ""
            ).startswith("https://"),
            "llama-model-sha-pinned": len(
                _env_value(env, "LLAMA_MODEL_SHA256") or ""
            ) == 64,
            "llama-model-url-revision-pinned": (
                "b69aef112e9f895e6f98d7ae0949f72ff09aa401"
                in (_env_value(env, "LLAMA_MODEL_URL") or "")
            ),
            "llama-one-thread": _env_value(env, "LLAMA_N_THREADS") == "1",
            "release-url-external": (
                release_url_item.get("sync") is False
                and "value" not in release_url_item
            ),
            "release-sha-pinned": (
                _env_value(env, "RUNTIME_RELEASE_SHA256")
                == "18ac85d3b2612a3057dd6e24660487457af078eb8abdf2bb94e122c9bc97c514"
            ),
            "omp-one-thread": _env_value(env, "OMP_NUM_THREADS") == "1",
            "mkl-one-thread": _env_value(env, "MKL_NUM_THREADS") == "1",
            "openblas-one-thread": _env_value(env, "OPENBLAS_NUM_THREADS") == "1",
            "numexpr-one-thread": _env_value(env, "NUMEXPR_NUM_THREADS") == "1",
            "tokenizers-no-parallelism": (
                _env_value(env, "TOKENIZERS_PARALLELISM") or ""
            ).lower() == "false",
        }
    )
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise DeploymentValidationError(
            "Blueprint incompatible con el perfil CPU F.11 de Llama real: "
            + ", ".join(failed)
        )
    return sorted(checks)


def main() -> int:
    path = Path("render.yaml")
    try:
        checks = validate_render_blueprint(path)
    except (OSError, yaml.YAMLError, DeploymentValidationError) as exc:
        print(f"ERROR: {exc}")
        return 1
    print(f"OK: render.yaml validado; {len(checks)} controles de despliegue.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
