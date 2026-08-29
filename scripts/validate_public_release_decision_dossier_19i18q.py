from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.services.public_release_decision_dossier_19i18q import (
    PublicationDecisionError,
    execute,
)

DEFAULT_PREPRODUCTION = Path(
    "reports/sprint19I18P/preproduction_gate_acceptance.json"
)
DEFAULT_MODEL_EVIDENCE = Path(
    "evidence/publication/model_license_paraphrase_multilingual_minilm.json"
)
DEFAULT_OUTPUT = Path("reports/sprint19I18Q")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Sprint 19I.18Q: expediente de decisión de publicación."
    )
    value.add_argument(
        "--preproduction",
        type=Path,
        default=DEFAULT_PREPRODUCTION,
    )
    value.add_argument(
        "--model-license-evidence",
        type=Path,
        default=DEFAULT_MODEL_EVIDENCE,
    )
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        report = execute(
            preproduction_report_path=args.preproduction,
            model_license_evidence_path=args.model_license_evidence,
            output_dir=args.output,
        )
    except PublicationDecisionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("OK: Sprint 19I.18Q; expediente de decisión consolidado")
    for key in (
        "technical_preproduction_complete",
        "model_license_metadata_verified",
        "model_license_review_required",
        "temporal_fail_closed_policy_ready",
        "temporal_policy_human_acceptance_required",
        "redistribution_human_review_required",
        "publication_legal_acceptance",
        "public_release_allowed",
        "git_push_allowed",
        "github_release_allowed",
        "render_deploy_allowed",
        "decision",
    ):
        print(f"- {key}={report[key]}")
    print(
        "- remaining_human_decisions="
        + ",".join(report["remaining_human_decisions"])
    )
    print(f"- report={args.output / 'publication_decision_dossier.json'}")
    print(f"- human_template={args.output / 'human_decision_template.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
