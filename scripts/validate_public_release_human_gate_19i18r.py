from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.services.public_release_human_gate_19i18r import (
    HumanReleaseDecisionError,
    execute,
)

DEFAULT_DOSSIER = Path("reports/sprint19I18Q/publication_decision_dossier.json")
DEFAULT_DECISION = Path("evidence/publication/human_release_decision_19i18r.json")
DEFAULT_OUTPUT = Path("reports/sprint19I18R/human_release_gate_acceptance.json")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Sprint 19I.18R: registro humano y gate de publicación."
    )
    value.add_argument("--dossier", type=Path, default=DEFAULT_DOSSIER)
    value.add_argument("--decision", type=Path, default=DEFAULT_DECISION)
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        report = execute(
            dossier_path=args.dossier,
            human_decision_path=args.decision,
            output_path=args.output,
        )
    except HumanReleaseDecisionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("OK: Sprint 19I.18R; decisión humana registrada y gate autorizado")
    for key in (
        "human_decision_record_complete",
        "temporal_fail_closed_release_policy_accepted",
        "normative_text_redistribution_approved",
        "publication_legal_acceptance",
        "public_release_allowed",
        "git_push_allowed",
        "github_release_allowed",
        "render_deploy_allowed",
        "decision",
    ):
        print(f"- {key}={report[key]}")
    print(f"- report={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
