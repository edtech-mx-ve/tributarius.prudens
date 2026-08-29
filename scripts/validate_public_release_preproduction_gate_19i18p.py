from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.services.public_release_preproduction_gate_19i18p import (
    PreproductionGateError,
    execute,
)

DEFAULT_19L = Path(
    "reports/sprint19I18L/public_runtime_legal_provenance_temporal.json"
)
DEFAULT_19M = Path(
    "dist/public_release_candidate_19i18m/release_candidate_acceptance.json"
)
DEFAULT_19N = Path(
    "dist/public_release_cold_start_19i18n/cold_start_acceptance.json"
)
DEFAULT_19O = Path(
    "dist/public_release_deployment_dependency_19i18o/"
    "deployment_dependency_acceptance.json"
)
DEFAULT_CANDIDATE = Path(
    "dist/public_release_candidate_19i18m/"
    "tributarius-prudens-public-runtime-candidate.zip"
)
DEFAULT_OUTPUT = Path(
    "reports/sprint19I18P/preproduction_gate_acceptance.json"
)


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description="Sprint 19I.18P: gate integral local de preproducción."
    )
    value.add_argument("--report-19l", type=Path, default=DEFAULT_19L)
    value.add_argument("--report-19m", type=Path, default=DEFAULT_19M)
    value.add_argument("--report-19n", type=Path, default=DEFAULT_19N)
    value.add_argument("--report-19o", type=Path, default=DEFAULT_19O)
    value.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    value.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        report = execute(
            report_19l_path=args.report_19l,
            report_19m_path=args.report_19m,
            report_19n_path=args.report_19n,
            report_19o_path=args.report_19o,
            candidate_zip=args.candidate,
            output_path=args.output,
        )
    except PreproductionGateError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print("OK: Sprint 19I.18P; gate integral local de preproducción consolidado")
    for key in (
        "technical_chain_complete",
        "runtime_integrity_complete",
        "cold_start_complete",
        "embedding_dependency_complete",
        "publication_legal_acceptance",
        "temporal_validity_complete",
        "redistribution_human_review_required",
        "public_release_allowed",
        "git_push_allowed",
        "github_release_allowed",
        "render_deploy_allowed",
        "decision",
    ):
        print(f"- {key}={report[key]}")
    print(f"- remaining_blockers={','.join(report['remaining_blockers'])}")
    print(f"- report={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
