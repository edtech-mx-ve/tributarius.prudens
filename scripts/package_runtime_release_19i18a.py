from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_release_bundle import (
    RuntimeReleaseBundleError,
    build_runtime_release_bundle,
    validate_runtime_release_bundle,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18A: empaqueta el runtime semántico v2 y el registro "
            "temporal en un ZIP determinista para publicación posterior."
        )
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=Path("deployment/runtime_artifacts_semantic_v2"),
    )
    parser.add_argument(
        "--temporal-registry",
        type=Path,
        default=Path("knowledge/temporal/temporal_provenance_registry.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "dist/runtime_release_19i18/"
            "tributarius-prudens-runtime-semantic-v2.zip"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        built = build_runtime_release_bundle(
            runtime_dir=args.runtime_dir,
            temporal_registry=args.temporal_registry,
            output_path=args.output,
        )
        validated = validate_runtime_release_bundle(args.output)
    except RuntimeReleaseBundleError as exc:
        print(f"ERROR: {exc}")
        return 1

    if built.bundle_sha256 != validated.bundle_sha256:
        print("ERROR: SHA-256 cambió entre construcción y validación.")
        return 2

    print("OK: Sprint 19I.18A; bundle runtime construido y validado")
    print(f"- output={built.output_path}")
    print(f"- bundle_sha256={built.bundle_sha256}")
    print(f"- bundle_size_bytes={built.bundle_size_bytes}")
    print(f"- runtime_chunk_count={built.runtime_chunk_count}")
    print(f"- runtime_vector_dimension={built.runtime_vector_dimension}")
    print(f"- runtime_model_name={built.runtime_model_name}")
    print(
        "- temporal_blocked_documents="
        f"{','.join(built.temporal_blocked_documents)}"
    )
    print(f"- packaged_files={len(built.packaged_files)}")
    print(
        "POLICY: este ZIP es un artefacto de release local; permanece bajo dist/ "
        "y no debe añadirse al repositorio Git."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
