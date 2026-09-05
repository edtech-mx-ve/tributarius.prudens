from types import SimpleNamespace

from app.services.focused_normative_rag import (
    _ScoredHit,
    _select_diverse_candidates,
)


def _exact(chunk_id: str, source_rank: int) -> _ScoredHit:
    return _ScoredHit(
        hit=SimpleNamespace(chunk_id=chunk_id),
        exact_seed=True,
        source_rank=source_rank,
        source_relevance_score=1.0,
        final_score=1.0,
    )


def test_exact_seeds_are_distributed_across_focal_sources() -> None:
    candidates = {
        "cff-1": _exact("cff-1", 1),
        "cff-2": _exact("cff-2", 1),
        "cff-3": _exact("cff-3", 1),
        "cff-4": _exact("cff-4", 1),
        "cff-5": _exact("cff-5", 1),
        "cff-6": _exact("cff-6", 1),
        "cff-7": _exact("cff-7", 1),
        "lisr-100": _exact("lisr-100", 2),
        "lisr-110": _exact("lisr-110", 2),
        "lfdc-2": _exact("lfdc-2", 5),
        "lfdc-3": _exact("lfdc-3", 5),
    }

    selected = _select_diverse_candidates(
        candidates,
        top_k=5,
    )

    ids = [item.hit.chunk_id for item in selected]

    assert len(ids) == 5
    assert "lisr-100" in ids
    assert "lisr-110" in ids
    assert any(item.startswith("cff-") for item in ids)
    assert any(item.startswith("lfdc-") for item in ids)
