from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_selective_rebuild_plan import (
    SelectiveRebuildPlanError,
    build_selective_rebuild_plan,
)

DEFAULT_INPUT = Path(
    "reports/sprint19I18J11/pdf_differential_diagnostic.json"
)
DEFAULT_OUTPUT = Path(
    "reports/sprint19I18J12/selective_rebuild_plan.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18J.12: genera un plan fail-closed de "
            "reconstrucción selectiva sin modificar el corpus."
        )
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        report = build_selective_rebuild_plan(
            differential_report_path=args.input,
            output_path=args.output,
        )
    except SelectiveRebuildPlanError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19I.18J.12; plan selectivo generado")
    print(f"- target_documents={','.join(report['target_documents'])}")
    print(f"- target_count={report['target_count']}")
    print(f"- rebuild_authorized={report['rebuild_authorized']}")
    print(f"- rebuild_executed={report['rebuild_executed']}")
    print("- public_release_allowed=False")
    print("- git_push_allowed=False")
    print("- github_release_allowed=False")
    print("- render_deploy_allowed=False")
    print(f"- report={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
