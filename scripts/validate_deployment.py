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
        "plan=free": service.get("plan") == "free",
        "health=/health": service.get("healthCheckPath") == "/health",
        "start-binds-host": "0.0.0.0" in str(service.get("startCommand", "")),
        "start-uses-port": "$PORT" in str(service.get("startCommand", "")),
        "build-installs-package": "pip install -e ." in build_command,
        "build-bootstraps-runtime": (
            "scripts.bootstrap_runtime_release_19i18c" in build_command
        ),
        "no-databases": "databases" not in payload,
        "no-disk": "disk" not in service and "diskPath" not in service,
    }
    env = _env_items(service)
    release_url_item = env.get("RUNTIME_RELEASE_URL", {})
    checks.update(
        {
            "environment=production": (
                _env_value(env, "ENVIRONMENT") == "production"
            ),
            "deployment=render": (
                _env_value(env, "DEPLOYMENT_PLATFORM") == "render"
            ),
            "stateless-profile": (
                _env_value(env, "RUNTIME_PROFILE") == "stateless_free"
            ),
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
            "rag-local-only": (
                _env_value(env, "RAG_LOCAL_FILES_ONLY") or ""
            ).lower() == "true",
            "rag-integrity-required": (
                _env_value(env, "VERIFY_RAG_INTEGRITY") or ""
            ).lower() == "true",
            "temporal-registry-required": (
                _env_value(env, "REQUIRE_TEMPORAL_PROVENANCE_REGISTRY") or ""
            ).lower() == "true",
            "release-url-external": (
                release_url_item.get("sync") is False
                and "value" not in release_url_item
            ),
            "release-sha-pinned": (
                _env_value(env, "RUNTIME_RELEASE_SHA256")
                == "4766b49014c5f40aa509b325ddb7268ca7032348559937d2ebae74b0dcefe360"
            ),
        }
    )
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise DeploymentValidationError(
            "Blueprint incompatible con el perfil gratuito: " + ", ".join(failed)
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
