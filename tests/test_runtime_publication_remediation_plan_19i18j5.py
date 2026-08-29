from __future__ import annotations

import json
from pathlib import Path

from app.services.runtime_publication_remediation_plan import (
    build_publication_remediation_plan,
)


def _write(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_plan_prioritizes_official_provenance_before_publication(
    tmp_path: Path,
) -> None:
    matrix = tmp_path / "matrix.json"
    gate = tmp_path / "gate.json"

    _write(
        matrix,
        {
            "observed_documents": 4,
            "publication_ready_documents": [],
            "blocked_documents": [
                "cff",
                "manual",
                "prodecon",
                "rmf_2026",
            ],
            "public_release_allowed": False,
        },
    )
    _write(
        gate,
        {
            "official_provenance_pending_documents": ["cff"],
            "separate_review_documents": ["manual", "prodecon"],
            "legal_basis_candidate_documents": ["rmf_2026"],
            "redistribution_review_pending_documents": [
                "cff",
                "manual",
                "prodecon",
                "rmf_2026",
            ],
        },
    )

    plan = build_publication_remediation_plan(
        decision_matrix_path=matrix,
        legal_gate_path=gate,
    )

    assert plan.next_safe_action == "acquire_official_evidence_19i18j2"
    assert plan.public_release_allowed is False
    assert plan.github_release_allowed is False
    assert plan.render_deploy_allowed is False
    assert [track.track_id for track in plan.tracks] == [
        "A_official_provenance",
        "B_normative_redistribution_review",
        "C_separate_license_review",
    ]


def test_plan_never_automates_legal_or_license_decisions(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.json"
    gate = tmp_path / "gate.json"

    _write(
        matrix,
        {
            "observed_documents": 3,
            "publication_ready_documents": [],
            "blocked_documents": ["manual", "prodecon", "rmf_2026"],
            "public_release_allowed": False,
        },
    )
    _write(
        gate,
        {
            "official_provenance_pending_documents": [],
            "separate_review_documents": ["manual", "prodecon"],
            "legal_basis_candidate_documents": ["rmf_2026"],
            "redistribution_review_pending_documents": [
                "manual",
                "prodecon",
                "rmf_2026",
            ],
        },
    )

    plan = build_publication_remediation_plan(
        decision_matrix_path=matrix,
        legal_gate_path=gate,
    )

    by_id = {track.track_id: track for track in plan.tracks}
    assert by_id["B_normative_redistribution_review"].automation_allowed is False
    assert by_id["C_separate_license_review"].automation_allowed is False
    assert plan.next_safe_action == "explicit_normative_redistribution_review"


def test_ready_and_blocked_coverage_must_be_consistent(tmp_path: Path) -> None:
    matrix = tmp_path / "matrix.json"
    gate = tmp_path / "gate.json"

    _write(
        matrix,
        {
            "observed_documents": 2,
            "publication_ready_documents": [],
            "blocked_documents": ["cff"],
            "public_release_allowed": False,
        },
    )
    _write(
        gate,
        {
            "official_provenance_pending_documents": ["cff"],
            "separate_review_documents": [],
            "legal_basis_candidate_documents": [],
            "redistribution_review_pending_documents": ["cff"],
        },
    )

    from app.services.runtime_official_source_audit import OfficialSourceAuditError

    try:
        build_publication_remediation_plan(
            decision_matrix_path=matrix,
            legal_gate_path=gate,
        )
    except OfficialSourceAuditError as exc:
        assert "Cobertura inconsistente" in str(exc)
    else:
        raise AssertionError("Se esperaba OfficialSourceAuditError")
