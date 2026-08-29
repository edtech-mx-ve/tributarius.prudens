from __future__ import annotations

from pathlib import Path

from app.services.runtime_official_source_audit import OfficialSourceAuditError
from app.services.runtime_publication_remediation_plan import (
    build_publication_remediation_plan,
    write_publication_remediation_plan,
)


def main() -> int:
    try:
        plan = build_publication_remediation_plan(
            decision_matrix_path=Path(
                "reports/sprint19I18J3/runtime_publication_decision_matrix.json"
            ),
            legal_gate_path=Path(
                "reports/sprint19I18J4/runtime_normative_legal_basis_gate.json"
            ),
        )
        report = Path(
            "reports/sprint19I18J5/runtime_publication_remediation_plan.json"
        )
        write_publication_remediation_plan(plan, report)
    except OfficialSourceAuditError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18J.5; plan de remediación de publicación generado")
    print(f"- observed_documents={plan.observed_documents}")
    print("- ready_documents=" + ",".join(plan.ready_documents))
    print("- blocked_documents=" + ",".join(plan.blocked_documents))
    print(f"- next_safe_action={plan.next_safe_action}")
    print(f"- git_push_allowed={plan.git_push_allowed}")
    print(f"- github_release_allowed={plan.github_release_allowed}")
    print(f"- render_deploy_allowed={plan.render_deploy_allowed}")
    print(f"- public_release_allowed={plan.public_release_allowed}")
    for track in plan.tracks:
        print(
            f"  {track.track_id}: documents={','.join(track.documents)}; "
            f"blocker={track.blocker}; "
            f"automation_allowed={track.automation_allowed}"
        )
    print(f"- report={report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
