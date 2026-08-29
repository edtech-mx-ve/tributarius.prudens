from __future__ import annotations

import argparse
from pathlib import Path

from app.services.selective_official_corpus_rebuild import (
    SelectiveOfficialRebuildError,
    stage_official_rebuild,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "J.12.1: reconstruye aisladamente la integración desde los PDF "
            "oficiales de LFDC y Reglamento LIVA, sin mutar el corpus canónico."
        )
    )
    parser.add_argument("--local-corpus-dir", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--plan",
        type=Path,
        default=Path("reports/sprint19I18J12/selective_rebuild_plan.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("dist/selective_rebuild_19i18j12_1"),
    )
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    try:
        stage_official_rebuild(
            project_root=args.project_root,
            local_corpus_dir=args.local_corpus_dir,
            plan_path=args.plan,
            output_dir=args.output_dir,
            overwrite=args.overwrite,
        )
    except SelectiveOfficialRebuildError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19I.18J.12.1; reconstrucción aislada completada")
    print("- target_documents=lfdc,reg_liva_250914")
    print("- local_corpus_mutated=False")
    print("- canonical_semantic_mutated=False")
    print("- runtime_index_mutated=False")
    print("- staged_integration_completed=True")
    print("- public_release_allowed=False")
    print(f"- output_dir={args.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
