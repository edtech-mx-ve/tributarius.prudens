from app.domain.cbr import CaseStatus, CBRCase, RetentionStatus
from app.services.cbr_retention import create_retention_candidate


def test_retention_candidate_is_pending_and_not_active() -> None:
    case = CBRCase(
        case_id="CASE-NEW",
        status=CaseStatus.ACTIVE,
        taxpayer_type="individual",
        activity="servicios",
        tax="ISR",
        problem_type="obligaciones",
        fiscal_year=2026,
        resolution_summary="Caso candidato.",
        source_refs=["SRC"],
    )
    candidate = create_retention_candidate(
        case,
        utility_reason="Aporta un patrón no cubierto.",
    )
    assert candidate.status == RetentionStatus.PENDING_REVIEW
    assert candidate.proposed_case.status == CaseStatus.HISTORICAL
