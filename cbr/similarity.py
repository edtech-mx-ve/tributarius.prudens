from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Mapping

from app.domain.cbr import CaseField, CBRCase, CBRQuery, FieldSimilarity

TOKEN_RE = re.compile(r"[a-z0-9]+")

FIELD_WEIGHTS: dict[CaseField, float] = {
    CaseField.TAXPAYER_TYPE: 0.18,
    CaseField.ACTIVITY: 0.16,
    CaseField.TAX: 0.18,
    CaseField.PROBLEM_TYPE: 0.18,
    CaseField.AUTHORITY_ACT: 0.10,
    CaseField.PROCEDURAL_STAGE: 0.10,
    CaseField.FISCAL_YEAR: 0.10,
}

EXACT_FIELDS = frozenset(
    {
        CaseField.TAXPAYER_TYPE,
        CaseField.TAX,
    }
)
SEMANTIC_TOKEN_FIELDS = frozenset(
    {
        CaseField.ACTIVITY,
        CaseField.PROBLEM_TYPE,
    }
)
OPTIONAL_EXACT_FIELDS = frozenset(
    {
        CaseField.AUTHORITY_ACT,
        CaseField.PROCEDURAL_STAGE,
    }
)


def normalize_text(value: str | None) -> str:
    if value is None:
        return ""
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return " ".join(TOKEN_RE.findall(without_marks.lower()))


def token_set(value: str | None) -> set[str]:
    return set(normalize_text(value).split())


def jaccard_similarity(left: str | None, right: str | None) -> float:
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def exact_similarity(left: str | None, right: str | None) -> float:
    return 1.0 if normalize_text(left) == normalize_text(right) else 0.0


def fiscal_year_similarity(query_year: int, case_year: int) -> float:
    distance = abs(query_year - case_year)
    if distance == 0:
        return 1.0
    if distance == 1:
        return 0.5
    return 0.0


def _field_score(
    field: CaseField,
    query: CBRQuery,
    case: CBRCase,
) -> FieldSimilarity:
    if field == CaseField.TAXPAYER_TYPE:
        query_value = query.taxpayer_type
        case_value = case.taxpayer_type
        score = exact_similarity(query_value, case_value)
    elif field == CaseField.ACTIVITY:
        query_value = query.activity
        case_value = case.activity
        score = jaccard_similarity(query_value, case_value)
    elif field == CaseField.TAX:
        query_value = query.tax
        case_value = case.tax
        score = exact_similarity(query_value, case_value)
    elif field == CaseField.PROBLEM_TYPE:
        query_value = query.problem_type
        case_value = case.problem_type
        score = jaccard_similarity(query_value, case_value)
    elif field == CaseField.AUTHORITY_ACT:
        query_value = query.authority_act or ""
        case_value = case.authority_act or ""
        if not query_value and not case_value:
            return FieldSimilarity(
                field=field,
                score=0.0,
                weight=0.0,
                query_value="",
                case_value="",
            )
        score = exact_similarity(query_value, case_value)
    elif field == CaseField.PROCEDURAL_STAGE:
        query_value = query.procedural_stage or ""
        case_value = case.procedural_stage or ""
        if not query_value and not case_value:
            return FieldSimilarity(
                field=field,
                score=0.0,
                weight=0.0,
                query_value="",
                case_value="",
            )
        score = exact_similarity(query_value, case_value)
    else:
        query_value = str(query.fiscal_year)
        case_value = str(case.fiscal_year)
        score = fiscal_year_similarity(query.fiscal_year, case.fiscal_year)

    return FieldSimilarity(
        field=field,
        score=score,
        weight=FIELD_WEIGHTS[field],
        query_value=query_value,
        case_value=case_value,
    )


def case_similarity(
    query: CBRQuery,
    case: CBRCase,
) -> tuple[float, list[FieldSimilarity]]:
    field_scores = [_field_score(field, query, case) for field in FIELD_WEIGHTS]
    active_scores = [item for item in field_scores if item.weight > 0]
    weighted = sum(item.score * item.weight for item in active_scores)
    total_weight = sum(item.weight for item in active_scores)
    if total_weight == 0:
        return 0.0, field_scores
    return weighted / total_weight, field_scores


def explain_similarity(field_scores: Iterable[FieldSimilarity]) -> str:
    scores = list(field_scores)
    active = [item for item in scores if item.weight > 0]
    ordered = sorted(
        active,
        key=lambda item: (
            item.score * item.weight,
            item.weight,
            item.field.value,
        ),
        reverse=True,
    )
    strongest = ordered[:3]
    parts = [
        f"{item.field.value}={item.score:.2f}"
        for item in strongest
    ]

    mismatches = [
        item.field.value
        for item in active
        if item.score == 0.0
    ]
    explanation = "Coincidencias principales: " + ", ".join(parts) + "."
    if mismatches:
        explanation += " Diferencias: " + ", ".join(sorted(mismatches)) + "."
    return explanation


def set_jaccard_similarity(left: Iterable[str], right: Iterable[str]) -> float:
    """Jaccard determinista para facetas jurídicas ya normalizadas."""
    left_values = {normalize_text(value) for value in left if normalize_text(value)}
    right_values = {normalize_text(value) for value in right if normalize_text(value)}
    if not left_values and not right_values:
        return 1.0
    if not left_values or not right_values:
        return 0.0
    return len(left_values & right_values) / len(left_values | right_values)


def partial_case_similarity(
    left: Mapping[CaseField, str | int | None],
    right: Mapping[CaseField, str | int | None],
) -> tuple[float, list[FieldSimilarity]]:
    """Extiende la similitud CBR existente a perfiles con campos aún incompletos.

    C.9 reutiliza exactamente ``FIELD_WEIGHTS`` y las mismas funciones de
    comparación del motor CBR. Si cualquiera de los dos perfiles carece de un
    campo, ese campo queda fuera del denominador en lugar de tratarse como una
    diferencia inventada.
    """
    field_scores: list[FieldSimilarity] = []
    for field in FIELD_WEIGHTS:
        left_value = left.get(field)
        right_value = right.get(field)
        if left_value is None or right_value is None:
            field_scores.append(
                FieldSimilarity(
                    field=field,
                    score=0.0,
                    weight=0.0,
                    query_value="" if left_value is None else str(left_value),
                    case_value="" if right_value is None else str(right_value),
                )
            )
            continue

        left_text = str(left_value)
        right_text = str(right_value)
        if field in EXACT_FIELDS or field in OPTIONAL_EXACT_FIELDS:
            score = exact_similarity(left_text, right_text)
        elif field in SEMANTIC_TOKEN_FIELDS:
            score = jaccard_similarity(left_text, right_text)
        else:
            score = fiscal_year_similarity(int(left_value), int(right_value))
        field_scores.append(
            FieldSimilarity(
                field=field,
                score=score,
                weight=FIELD_WEIGHTS[field],
                query_value=left_text,
                case_value=right_text,
            )
        )

    active_scores = [item for item in field_scores if item.weight > 0]
    if not active_scores:
        return 0.0, field_scores
    weighted = sum(item.score * item.weight for item in active_scores)
    total_weight = sum(item.weight for item in active_scores)
    return weighted / total_weight, field_scores


def critical_field_conflicts(
    field_scores: Iterable[FieldSimilarity],
    critical_fields: Iterable[CaseField],
) -> list[CaseField]:
    """Devuelve conflictos observables; los campos desconocidos no se inventan."""
    critical = set(critical_fields)
    return [
        item.field
        for item in field_scores
        if item.field in critical and item.weight > 0 and item.score != 1.0
    ]
