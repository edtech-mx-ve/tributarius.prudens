from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_release_publication_plan import (
    RuntimeReleasePublicationPlanError,
    build_publication_plan,
)

_APPROVED_SHA256 = (
    "687c9f6bba0b166b3728ce387d560644523d260cde1f7a298655954e490cbda4"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18D: prepara localmente un plan reproducible para "
            "publicar el bundle runtime como GitHub Release asset."
        )
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path(
            "dist/runtime_release_19i18/"
            "tributarius-prudens-runtime-semantic-v2.zip"
        ),
    )
    parser.add_argument(
        "--sha256",
        default=_APPROVED_SHA256,
    )
    parser.add_argument(
        "--repository",
        default="edtech-mx-ve/tributarius.prudens",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/runtime_release_19i18/publication"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        plan = build_publication_plan(
            bundle_path=args.bundle,
            expected_sha256=args.sha256,
            repository=args.repository,
            output_dir=args.output_dir,
        )
    except RuntimeReleasePublicationPlanError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.18D; plan local de publicación generado")
    print(f"- repository={plan.repository}")
    print(f"- tag={plan.tag}")
    print(f"- asset_name={plan.asset_name}")
    print(f"- asset_sha256={plan.asset_sha256}")
    print(f"- asset_size_bytes={plan.asset_size_bytes}")
    print(f"- release_url={plan.release_url}")
    print(f"- asset_url={plan.asset_url}")
    print(f"- notes={plan.release_notes_path}")
    print(f"- plan={plan.plan_path}")
    print(
        "POLICY: este comando no publica nada; solo prepara y valida el plan "
        "local para el release."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
