from __future__ import annotations

import argparse
import os
from pathlib import Path

from app.services.runtime_release_installer import (
    RuntimeReleaseInstallError,
    install_runtime_release,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18B: instala de forma verificable un bundle runtime "
            "desde HTTPS o desde una ruta local explícita."
        )
    )
    parser.add_argument(
        "--source",
        default=os.getenv("RUNTIME_RELEASE_URL", ""),
        help="URL HTTPS o ruta local del bundle.",
    )
    parser.add_argument(
        "--sha256",
        default=os.getenv("RUNTIME_RELEASE_SHA256", ""),
        help="SHA-256 esperado del bundle.",
    )
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path("."),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=60.0,
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=100_000_000,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.source.strip():
        print("ERROR: falta --source o RUNTIME_RELEASE_URL.")
        return 2
    if not args.sha256.strip():
        print("ERROR: falta --sha256 o RUNTIME_RELEASE_SHA256.")
        return 2

    try:
        summary = install_runtime_release(
            source=args.source.strip(),
            expected_sha256=args.sha256.strip(),
            project_root=args.project_root,
            timeout_seconds=args.timeout_seconds,
            max_bytes=args.max_bytes,
        )
    except RuntimeReleaseInstallError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.18B; runtime instalado y verificado")
    print(f"- source={summary.source}")
    print(f"- bundle_sha256={summary.bundle_sha256}")
    print(f"- bundle_size_bytes={summary.bundle_size_bytes}")
    print(f"- runtime_dir={summary.runtime_dir}")
    print(f"- temporal_registry={summary.temporal_registry}")
    print(f"- installed_files={len(summary.installed_files)}")
    print(
        "POLICY: la instalación exige SHA-256 exacto, contenido permitido y "
        "validación interna antes de activar el runtime."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
