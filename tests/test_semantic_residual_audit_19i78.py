from __future__ import annotations

from app.services.semantic_residual_audit import SemanticResidualReport


def test_report_dataclass_accepts_empty_findings() -> None:
    report = SemanticResidualReport(
        total_residuals=0,
        safe_absorptions=0,
        requires_review=0,
        classifications={},
        findings=(),
    )
    assert report.total_residuals == 0
    assert report.findings == ()
