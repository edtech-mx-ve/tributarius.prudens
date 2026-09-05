from __future__ import annotations

from app.domain.cbr import CBRQuery
from app.domain.query import QueryAnalysis, QueryDimensionName


def _dimension_values(
    analysis: QueryAnalysis,
    dimension: QueryDimensionName,
) -> list[str]:
    multidimensional = analysis.multidimensional
    if multidimensional is None:
        return []

    values: list[str] = []
    seen: set[str] = set()

    for item in multidimensional.dimensions:
        if item.dimension is not dimension:
            continue

        clean = " ".join(item.value.split())
        key = clean.casefold()

        if clean and key not in seen:
            seen.add(key)
            values.append(clean)

    return values


def build_operational_cbr_query(
    analysis: QueryAnalysis,
    *,
    fiscal_year: int | None,
    top_k: int = 5,
) -> CBRQuery | None:
    """Construye CBRQuery s?lo desde dimensiones suficientes y no ambiguas.

    No inventa campos ausentes y no utiliza D.4 como precedente operativo.
    """
    multidimensional = analysis.multidimensional

    if (
        multidimensional is None
        or analysis.requires_clarification
        or fiscal_year is None
        or multidimensional.primary_problem_id is None
    ):
        return None

    taxpayer_types = _dimension_values(
        analysis,
        QueryDimensionName.TAXPAYER_TYPE,
    )
    activities = _dimension_values(
        analysis,
        QueryDimensionName.ACTIVITY,
    )
    taxes = _dimension_values(
        analysis,
        QueryDimensionName.TAX,
    )

    if (
        len(taxpayer_types) != 1
        or len(activities) != 1
        or len(taxes) != 1
    ):
        return None

    query_years = _dimension_values(
        analysis,
        QueryDimensionName.FISCAL_YEAR,
    )
    if len(query_years) > 1:
        return None

    if query_years:
        if not query_years[0].isdigit():
            return None
        if int(query_years[0]) != fiscal_year:
            return None

    authority_acts = _dimension_values(
        analysis,
        QueryDimensionName.AUTHORITY_ACT,
    )
    procedural_stages = _dimension_values(
        analysis,
        QueryDimensionName.PROCEDURAL_STAGE,
    )

    if len(authority_acts) > 1 or len(procedural_stages) > 1:
        return None

    return CBRQuery(
        taxpayer_type=taxpayer_types[0],
        activity=activities[0],
        tax=taxes[0],
        problem_type=multidimensional.primary_problem_id,
        authority_act=authority_acts[0] if authority_acts else None,
        procedural_stage=(
            procedural_stages[0]
            if procedural_stages
            else None
        ),
        fiscal_year=fiscal_year,
        top_k=top_k,
    )


def resolve_operational_cbr_query(
    analysis: QueryAnalysis,
    *,
    explicit_query: CBRQuery | None,
    fiscal_year: int | None,
    top_k: int = 5,
) -> CBRQuery | None:
    """Prioriza CBRQuery expl?cito; si falta, deriva uno seguro desde QueryAnalysis."""
    if explicit_query is not None:
        return explicit_query

    return build_operational_cbr_query(
        analysis,
        fiscal_year=fiscal_year,
        top_k=top_k,
    )
