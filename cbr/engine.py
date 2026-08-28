from __future__ import annotations

from app.domain.cbr import (
    CaseStatus,
    CBRCase,
    CBRMatch,
    CBRQuery,
    CBRRetrievalResult,
    FieldSimilarity,
)
from cbr.similarity import case_similarity, explain_similarity


def retrieve_similar_cases(
    query: CBRQuery,
    cases: list[CBRCase],
) -> CBRRetrievalResult:
    """Recupera casos semejantes sin permitir que sustituyan la normativa vigente."""
    candidates = [
        case
        for case in cases
        if case.status in {CaseStatus.ACTIVE, CaseStatus.HISTORICAL}
    ]

    scored: list[tuple[float, CBRCase, list[FieldSimilarity]]] = []
    for case in candidates:
        similarity, field_scores = case_similarity(query, case)
        scored.append((similarity, case, field_scores))

    scored.sort(key=lambda item: (-item[0], item[1].case_id))
    selected = scored[: query.top_k]

    matches = [
        CBRMatch(
            rank=index,
            case_id=case.case_id,
            status=case.status,
            similarity=round(similarity, 6),
            resolution_summary=case.resolution_summary,
            normative_refs=case.normative_refs,
            source_refs=case.source_refs,
            field_scores=field_scores,
            explanation=explain_similarity(field_scores),
            requires_human_review=(
                case.status != CaseStatus.ACTIVE or not case.normative_refs
            ),
        )
        for index, (similarity, case, field_scores) in enumerate(selected, start=1)
    ]

    return CBRRetrievalResult(
        query=query,
        candidate_count=len(candidates),
        returned_count=len(matches),
        matches=matches,
    )
