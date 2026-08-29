from __future__ import annotations

import argparse
from pathlib import Path

from app.services.runtime_official_provenance_reconciliation import (
    ProvenanceReconciliationError,
    reconcile_official_provenance,
)

DEFAULT_BROWSER = Path(
    "reports/sprint19I18J7/browser_official_evidence_bridge.json"
)
DEFAULT_ONLINE = Path(
    "reports/sprint19I18J/runtime_official_source_provenance.json"
)
DEFAULT_LOCAL = Path(
    "reports/sprint19I18I/runtime_source_bridge.json"
)
DEFAULT_CONFORMITY = Path(
    "reports/sprint19I18G/runtime_publication_content_conformity.json"
)
DEFAULT_LEGAL = Path(
    "reports/sprint19I18J4/runtime_normative_legal_basis_gate.json"
)
DEFAULT_POLICY = Path(
    "reports/sprint19I18E/runtime_publication_safety.json"
)
DEFAULT_TEMPORAL = Path(
    "knowledge/temporal/temporal_provenance_registry.json"
)
DEFAULT_OUTPUT = Path(
    "reports/sprint19I18J10/runtime_official_provenance_reconciliation.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Sprint 19I.18J.10: reconcilia procedencia oficial, "
            "conformidad, redistribución y vigencia sin auto-promoción."
        )
    )
    parser.add_argument("--browser-bridge", type=Path, default=DEFAULT_BROWSER)
    parser.add_argument("--online-provenance", type=Path, default=DEFAULT_ONLINE)
    parser.add_argument("--local-bridge", type=Path, default=DEFAULT_LOCAL)
    parser.add_argument("--conformity", type=Path, default=DEFAULT_CONFORMITY)
    parser.add_argument("--legal-basis", type=Path, default=DEFAULT_LEGAL)
    parser.add_argument("--publication-policy", type=Path, default=DEFAULT_POLICY)
    parser.add_argument("--temporal-registry", type=Path, default=DEFAULT_TEMPORAL)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    try:
        report = reconcile_official_provenance(
            browser_bridge_path=args.browser_bridge,
            online_provenance_path=args.online_provenance,
            local_bridge_path=args.local_bridge,
            conformity_path=args.conformity,
            legal_basis_path=args.legal_basis,
            publication_policy_path=args.publication_policy,
            temporal_registry_path=args.temporal_registry,
            output_path=args.output,
        )
    except ProvenanceReconciliationError as exc:
        print(f"ERROR: {exc}")
        return 3

    print("OK: Sprint 19I.18J.10; reconciliación completada")
    print(
        "- official_provenance_exact_normative_count="
        f"{report['official_provenance_exact_normative_count']}"
    )
    print(
        "- official_provenance_complete_for_normative_corpus="
        f"{report['official_provenance_complete_for_normative_corpus']}"
    )
    print(
        "- normative_publication_ready_documents="
        f"{','.join(report['normative_publication_ready_documents'])}"
    )
    print(
        "- separate_license_review_documents="
        f"{','.join(report['separate_license_review_documents'])}"
    )
    print(
        "- blocked_documents="
        f"{','.join(report['blocked_documents'])}"
    )
    print(f"- public_release_allowed={report['public_release_allowed']}")
    print("- git_push_allowed=False")
    print("- github_release_allowed=False")
    print("- render_deploy_allowed=False")
    print("- automatic_promotion_performed=False")
    print(f"- report={args.output}")

    return 0 if report["official_provenance_complete_for_normative_corpus"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
