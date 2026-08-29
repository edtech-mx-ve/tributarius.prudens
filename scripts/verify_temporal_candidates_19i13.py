from __future__ import annotations

import argparse
from pathlib import Path

from app.services.normative_temporal_candidate_verifier import (
    NormativeTemporalCandidateVerifierError,
    load_and_verify_candidates,
    write_verification_outputs,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.13: verifica alcance contextual de candidatos temporales "
            "LIVA/CPEUM sin promover fechas."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("reports/sprint19I12/priority_temporal_candidates.csv"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/sprint19I13"),
    )
    parser.add_argument("--context-radius", type=int, default=5)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = load_and_verify_candidates(
            input_csv=args.input,
            context_radius=args.context_radius,
        )
        outputs = write_verification_outputs(
            output_dir=args.output_dir,
            report=report,
        )
    except NormativeTemporalCandidateVerifierError as exc:
        print(f"ERROR: {exc}")
        return 1

    print("OK: Sprint 19I.13; candidatos temporales contextualizados")
    print(f"- input_candidates={report.input_candidates}")
    print(f"- explicit_date_candidates={report.explicit_date_candidates}")
    print(f"- verified_records={report.verified_records}")
    print(f"- whole_document_candidates={report.whole_document_candidates}")
    print(
        "- amendment_specific_candidates="
        f"{report.amendment_specific_candidates}"
    )
    print(
        "- ambiguous_scope_candidates="
        f"{report.ambiguous_scope_candidates}"
    )
    print(f"- promotion_ready={report.promotion_ready}")
    for record in report.records:
        print(
            f"  {record.canonical_id}:{record.line_number}; "
            f"date={record.explicit_date_signal}; "
            f"scope={record.scope_classification}; "
            f"class={record.classification}"
        )
    for label, path in outputs.items():
        print(f"- {label}={path}")
    print(
        "POLICY: ninguna fecha se promueve automáticamente; "
        "el alcance debe validarse antes del enriquecimiento."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
