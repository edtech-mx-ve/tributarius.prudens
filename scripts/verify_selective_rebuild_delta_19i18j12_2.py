from __future__ import annotations

import argparse
from pathlib import Path

from app.services.selective_rebuild_delta import (
    SelectiveRebuildDeltaError,
    verify_selective_delta,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="J.12.2: verifica el delta aislado antes de promoción."
    )
    parser.add_argument(
        "--current-manifest",
        type=Path,
        default=Path("knowledge/metadata/fiscal_corpus_15_manifest.json"),
    )
    parser.add_argument(
        "--staged-manifest",
        type=Path,
        default=Path(
            "dist/selective_rebuild_19i18j12_1/"
            "knowledge/metadata/fiscal_corpus_15_manifest.json"
        ),
    )
    parser.add_argument(
        "--current-normalized-root",
        type=Path,
        default=Path("knowledge/normalized"),
    )
    parser.add_argument(
        "--staged-normalized-root",
        type=Path,
        default=Path(
            "dist/selective_rebuild_19i18j12_1/knowledge/normalized"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "reports/sprint19I18J12_2/selective_rebuild_delta.json"
        ),
    )
    args = parser.parse_args()

    try:
        report = verify_selective_delta(
            current_manifest_path=args.current_manifest,
            staged_manifest_path=args.staged_manifest,
            current_normalized_root=args.current_normalized_root,
            staged_normalized_root=args.staged_normalized_root,
            output_path=args.output,
        )
    except SelectiveRebuildDeltaError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19I.18J.12.2; delta verificado")
    print(f"- document_count={report['document_count']}")
    print(
        "- source_changed_documents="
        + ",".join(report["source_changed_documents"])
    )
    print(
        "- normalized_changed_documents="
        + ",".join(report["normalized_changed_documents"])
    )
    print(
        "- unauthorized_changed_documents="
        + ",".join(report["unauthorized_changed_documents"])
    )
    print(
        "- delta_safe_for_candidate_build="
        f"{report['delta_safe_for_candidate_build']}"
    )
    print("- canonical_mutation_performed=False")
    print("- public_release_allowed=False")
    print(f"- report={args.output}")
    return 0 if report["delta_safe_for_candidate_build"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
