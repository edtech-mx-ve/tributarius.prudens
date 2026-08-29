from __future__ import annotations

import pytest

from app.services.semantic_corpus_promotion import (
    PromotionGateSummary,
    SemanticCorpusPromotionError,
    _assert_gate,
)


def _valid_gate() -> PromotionGateSummary:
    return PromotionGateSummary(
        baseline_chunks=3174,
        candidate_chunks=2981,
        candidate_sha256="a" * 64,
        duplicate_candidate_ids=0,
        candidate_empty_text=0,
        legitimate_boundaries_total=135,
        legitimate_boundaries_missing=0,
        duplicate_boundaries_total=18,
        duplicate_boundaries_unresolved=0,
        semantic_residuals_total=25,
        semantic_residuals_safe=4,
        semantic_residuals_review=21,
        source_residuals_total=21,
        source_residuals_safe=7,
        source_residuals_review=14,
        profile_cases_total=14,
        profile_cases_safe=14,
        profile_cases_review=0,
    )


def test_promotion_gate_accepts_closed_chain() -> None:
    _assert_gate(
        _valid_gate(),
        expected_baseline_chunks=3174,
        expected_candidate_chunks=2981,
    )


def test_promotion_gate_rejects_pending_profile_case() -> None:
    gate = _valid_gate()
    invalid = PromotionGateSummary(
        **{
            **gate.__dict__,
            "profile_cases_safe": 13,
            "profile_cases_review": 1,
        }
    )
    with pytest.raises(SemanticCorpusPromotionError):
        _assert_gate(
            invalid,
            expected_baseline_chunks=3174,
            expected_candidate_chunks=2981,
        )
