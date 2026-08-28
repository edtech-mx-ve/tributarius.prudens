from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class DeploymentValidationError(RuntimeError):
    pass


def _env_map(service: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in service.get("envVars", []):
        if not isinstance(item, dict):
            raise DeploymentValidationError("envVars contiene una entrada inválida.")
        key = item.get("key")
        value = item.get("value")
        if isinstance(key, str) and isinstance(value, str):
            result[key] = value
    return result


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

    checks = {
        "type=web": service.get("type") == "web",
        "runtime=python": service.get("runtime") == "python",
        "plan=free": service.get("plan") == "free",
        "health=/health": service.get("healthCheckPath") == "/health",
        "start-binds-host": "0.0.0.0" in str(service.get("startCommand", "")),
        "start-uses-port": "$PORT" in str(service.get("startCommand", "")),
        "no-databases": "databases" not in payload,
        "no-disk": "disk" not in service and "diskPath" not in service,
    }

    env = _env_map(service)
    checks.update(
        {
            "environment=production": env.get("ENVIRONMENT") == "production",
            "deployment=render": env.get("DEPLOYMENT_PLATFORM") == "render",
            "stateless-profile": env.get("RUNTIME_PROFILE") == "stateless_free",
            "sqlite-is-ephemeral": env.get("DATABASE_URL", "").startswith(
                "sqlite:////tmp/"
            ),
            "docs-disabled": env.get("ENABLE_DOCS", "").lower() == "false",
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
