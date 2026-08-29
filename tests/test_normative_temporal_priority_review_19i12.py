from __future__ import annotations

from app.services.normative_temporal_priority_review import (
    PriorityTemporalEvidence,
    build_priority_review_report,
    classify_temporal_line,
)


def test_classifies_entry_into_force_with_date_candidate() -> None:
    classification, date_signal = classify_temporal_line(
        "El presente Decreto entrará en vigor el 1 de enero de 2026."
    )
    assert classification == "strong_entry_into_force"
    assert date_signal == "1 de enero de 2026"


def test_publication_reference_is_not_promoted() -> None:
    classification, _ = classify_temporal_line(
        "A partir de su publicación en el Diario Oficial de la Federación."
    )
    assert classification == "publication_reference"


def test_report_is_fail_closed_for_promotion() -> None:
    record = PriorityTemporalEvidence(
        canonical_id="liva",
        source_path="liva.md",
        line_number=10,
        classification="strong_entry_into_force",
        explicit_date_signal="1 de enero de 2026",
        line="Entrará en vigor el 1 de enero de 2026.",
    )
    report = build_priority_review_report(
        records=[record],
        total_input_lines=1,
    )
    assert report.candidates_with_explicit_date_signal == 1
    assert report.promotion_ready == 0
