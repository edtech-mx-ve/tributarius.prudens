from __future__ import annotations

from pathlib import Path

from app.services.runtime_normative_legal_basis_gate import (
    evaluate_normative_legal_basis_gate,
    write_normative_legal_basis_gate_report,
)
from app.services.runtime_official_source_audit import OfficialSourceAuditError


def main() -> int:
    try:
        summary = evaluate_normative_legal_basis_gate(
            decision_matrix_path=Path(
                "reports/sprint19I18J3/runtime_publication_decision_matrix.json"
            ),
            evidence_registry_path=Path(
                "app/resources/runtime_publication_evidence_19i18f.json"
            ),
            legal_basis_registry_path=Path(
                "app/resources/runtime_normative_legal_basis_19i18j4.json"
            ),
        )
        report = Path(
            "reports/sprint19I18J4/runtime_normative_legal_basis_gate.json"
        )
        write_normative_legal_basis_gate_report(summary, report)
    except OfficialSourceAuditError as exc:
        print(f"ERROR: {exc}")
        return 2

    print("OK: Sprint 19I.18J.4; gate jurídico normativo auditado")
    print(f"- observed_documents={summary.observed_documents}")
    print(
        "- legal_basis_candidate_documents="
        + ",".join(summary.legal_basis_candidate_documents)
    )
    print(
        "- official_provenance_pending_documents="
        + ",".join(summary.official_provenance_pending_documents)
    )
    print(
        "- separate_review_documents="
        + ",".join(summary.separate_review_documents)
    )
    print(
        "- redistribution_review_pending_documents="
        + ",".join(summary.redistribution_review_pending_documents)
    )
    print(
        f"- automatic_promotion_performed="
        f"{summary.automatic_promotion_performed}"
    )
    print(f"- public_release_allowed={summary.public_release_allowed}")
    for item in summary.documents:
        print(
            f"  {item.document_id}: "
            f"legal_basis_candidate_supported="
            f"{item.legal_basis_candidate_supported}; "
            f"disposition={item.disposition}; "
            f"blockers={','.join(item.blockers)}"
        )
    print(f"- report={report}")
    print(
        "POLICY: este gate clasifica evidencia jurídica; no modifica la "
        "política 19I.18E ni autoriza publicación automáticamente."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
