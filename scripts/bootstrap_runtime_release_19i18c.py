from __future__ import annotations

import os
from pathlib import Path

from app.services.runtime_release_installer import (
    RuntimeReleaseInstallError,
    install_runtime_release,
)


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeReleaseInstallError(
            f"Falta variable de entorno obligatoria: {name}"
        )
    return value


def main() -> int:
    try:
        source = _required_env("RUNTIME_RELEASE_URL")
        expected_sha256 = _required_env("RUNTIME_RELEASE_SHA256")
        if not source.startswith("https://"):
            raise RuntimeReleaseInstallError(
                "RUNTIME_RELEASE_URL debe usar HTTPS en despliegue."
            )

        summary = install_runtime_release(
            source=source,
            expected_sha256=expected_sha256,
            project_root=Path("."),
            timeout_seconds=120.0,
            max_bytes=100_000_000,
        )
    except RuntimeReleaseInstallError as exc:
        print(f"ERROR: bootstrap runtime rechazado: {exc}")
        return 1

    print("OK: Sprint 19I.18C; runtime de despliegue instalado y verificado")
    print(f"- bundle_sha256={summary.bundle_sha256}")
    print(f"- bundle_size_bytes={summary.bundle_size_bytes}")
    print(f"- runtime_dir={summary.runtime_dir}")
    print(f"- temporal_registry={summary.temporal_registry}")
    print(f"- installed_files={len(summary.installed_files)}")
    print(
        "POLICY: el build falla si la URL, el SHA-256 o el contenido del "
        "bundle no son verificables."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
