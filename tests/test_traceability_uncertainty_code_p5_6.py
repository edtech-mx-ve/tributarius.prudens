import pytest
from pydantic import ValidationError

from app.domain.traceability import UncertaintyItem


def test_uncertainty_accepts_hyphenated_heuristic_code() -> None:
    item = UncertaintyItem(
        code="HEUR-NORM-001",
        message="Se?al heur?stica normativa.",
        stage="legal_heuristics",
        requires_human_review=True,
    )

    assert item.code == "HEUR-NORM-001"


def test_uncertainty_preserves_existing_underscore_code() -> None:
    item = UncertaintyItem(
        code="CBR_REUSE_REVIEW",
        message="Revisi?n CBR.",
        stage="cbr",
        requires_human_review=True,
    )

    assert item.code == "CBR_REUSE_REVIEW"


def test_uncertainty_rejects_unsupported_code_characters() -> None:
    with pytest.raises(ValidationError):
        UncertaintyItem(
            code="HEUR/NORM/001",
            message="C?digo inv?lido.",
            stage="legal_heuristics",
            requires_human_review=True,
        )
