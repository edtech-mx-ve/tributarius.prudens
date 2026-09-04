from __future__ import annotations

import calendar
import re
import unicodedata
from datetime import date
from typing import Literal

from app.domain.jurisprudence import (
    JurisprudenceCriterionType,
    JurisprudenceStatus,
)
from app.domain.jurisprudence_metadata import JurisprudenceMetadataRecord
from app.domain.jurisprudence_temporal import (
    JurisprudenceBindingTemporalState,
    JurisprudencePublicationDatePrecision,
    JurisprudencePublicationTemporalState,
    JurisprudenceTemporalAssessment,
    JurisprudenceTemporalRecord,
)

_DAY_MONTH_YEAR_RE = re.compile(
    r"(?i)(?:lunes|martes|mi[eé]rcoles|jueves|viernes|s[aá]bado|domingo)?\s*"
    r"(?P<day>\d{1,2})\s+de\s+(?P<month>[a-záéíóúñ]+)\s+de\s+(?P<year>\d{4})"
)
_MONTH_YEAR_RE = re.compile(
    r"(?i)^(?P<month>[a-záéíóúñ]+)\s+de\s+(?P<year>\d{4})$"
)
_YEAR_RE = re.compile(r"^(?P<year>\d{4})$")
_ISO_RE = re.compile(r"^(?P<year>\d{4})-(?P<month>\d{2})-(?P<day>\d{2})$")
_SLASH_RE = re.compile(r"^(?P<day>\d{1,2})/(?P<month>\d{1,2})/(?P<year>\d{4})$")

_MONTHS = {
    "enero": 1,
    "febrero": 2,
    "marzo": 3,
    "abril": 4,
    "mayo": 5,
    "junio": 6,
    "julio": 7,
    "agosto": 8,
    "septiembre": 9,
    "setiembre": 9,
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_STATUS_TERMS = {
    JurisprudenceStatus.SUPERSEDED: (
        "superada",
        "superado",
        "sustituida",
        "sustituido",
    ),
    JurisprudenceStatus.INVALIDATED: ("invalidada", "invalidado", "sin vigencia"),
    JurisprudenceStatus.HISTORICAL: ("historica", "historico"),
}


class JurisprudenceTemporalControlError(ValueError):
    pass


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    return "".join(
        char for char in decomposed if not unicodedata.combining(char)
    ).strip()


def _month_number(value: str) -> int | None:
    return _MONTHS.get(_normalize(value))


def _parse_date(
    raw: str | None,
) -> tuple[
    JurisprudencePublicationDatePrecision,
    date | None,
    date | None,
]:
    if raw is None or not raw.strip():
        return JurisprudencePublicationDatePrecision.UNKNOWN, None, None
    value = raw.strip()

    match = _DAY_MONTH_YEAR_RE.search(value)
    if match:
        month = _month_number(match.group("month"))
        if month is None:
            return JurisprudencePublicationDatePrecision.INVALID, None, None
        try:
            exact = date(int(match.group("year")), month, int(match.group("day")))
        except ValueError:
            return JurisprudencePublicationDatePrecision.INVALID, None, None
        return JurisprudencePublicationDatePrecision.DAY, exact, exact

    match = _ISO_RE.fullmatch(value) or _SLASH_RE.fullmatch(value)
    if match:
        try:
            exact = date(
                int(match.group("year")),
                int(match.group("month")),
                int(match.group("day")),
            )
        except ValueError:
            return JurisprudencePublicationDatePrecision.INVALID, None, None
        return JurisprudencePublicationDatePrecision.DAY, exact, exact

    match = _MONTH_YEAR_RE.fullmatch(value)
    if match:
        month = _month_number(match.group("month"))
        if month is None:
            return JurisprudencePublicationDatePrecision.INVALID, None, None
        year = int(match.group("year"))
        last_day = calendar.monthrange(year, month)[1]
        return (
            JurisprudencePublicationDatePrecision.MONTH,
            date(year, month, 1),
            date(year, month, last_day),
        )

    match = _YEAR_RE.fullmatch(value)
    if match:
        year = int(match.group("year"))
        return (
            JurisprudencePublicationDatePrecision.YEAR,
            date(year, 1, 1),
            date(year, 12, 31),
        )

    return JurisprudencePublicationDatePrecision.INVALID, None, None


def _status_pages(record: JurisprudenceMetadataRecord) -> list[int]:
    status = record.extracted.status
    terms = _STATUS_TERMS.get(status)
    if not terms:
        return []
    pages: list[int] = []
    for evidence in record.evidence:
        normalized = _normalize(evidence.value)
        if any(term in normalized for term in terms):
            pages.extend(evidence.source_pages)
    return sorted(set(pages))


def _field_pages(record: JurisprudenceMetadataRecord, field_name: str) -> list[int]:
    return sorted(
        {
            page
            for evidence in record.evidence
            if evidence.field_name == field_name
            for page in evidence.source_pages
        }
    )


def _binding_character(
    criterion_type: JurisprudenceCriterionType,
) -> tuple[
    bool,
    Literal[
        "official_type_jurisprudence",
        "official_type_not_jurisprudence",
        "official_type_unknown",
    ],
    bool,
]:
    if criterion_type is JurisprudenceCriterionType.JURISPRUDENCE:
        return True, "official_type_jurisprudence", True
    if criterion_type is JurisprudenceCriterionType.UNKNOWN:
        return False, "official_type_unknown", False
    return False, "official_type_not_jurisprudence", True


def build_jurisprudence_temporal_record(
    metadata_record: JurisprudenceMetadataRecord,
) -> JurisprudenceTemporalRecord:
    """E.4: tipo Jurisprudencia fija obligatoriedad; la fecha fija sus efectos."""

    publication_precision, publication_start, publication_end = _parse_date(
        metadata_record.extracted.publication_date_text
    )
    binding_precision, binding_start, binding_end = _parse_date(
        metadata_record.extracted.binding_effective_date_text
    )
    mandatory, basis, binding_evaluated = _binding_character(
        metadata_record.extracted.criterion_type
    )

    return JurisprudenceTemporalRecord(
        document_id=metadata_record.document_id,
        source_sha256=metadata_record.source_sha256,
        criterion_type=metadata_record.extracted.criterion_type,
        publication_date_text=metadata_record.extracted.publication_date_text,
        parsed_publication_start=publication_start,
        parsed_publication_end=publication_end,
        publication_date_precision=publication_precision,
        publication_date_source_pages=_field_pages(
            metadata_record, "publication_date_text"
        ),
        binding_character_mandatory=mandatory,
        binding_character_basis=basis,
        binding_effective_date_text=(
            metadata_record.extracted.binding_effective_date_text
        ),
        parsed_binding_start=binding_start,
        parsed_binding_end=binding_end,
        binding_date_precision=binding_precision,
        binding_date_source_pages=_field_pages(
            metadata_record, "binding_effective_date_text"
        ),
        criterion_status_claim=metadata_record.extracted.status,
        status_claim_source_pages=_status_pages(metadata_record),
        binding_force_evaluated=binding_evaluated,
    )


def _publication_assessment(
    record: JurisprudenceTemporalRecord,
    query_date: date,
) -> tuple[
    JurisprudencePublicationTemporalState,
    bool | None,
    bool,
    list[str],
]:
    start = record.parsed_publication_start
    end = record.parsed_publication_end
    precision = record.publication_date_precision

    if start is None or end is None:
        return (
            JurisprudencePublicationTemporalState.UNKNOWN,
            None,
            False,
            [f"publication_date_{precision.value}"],
        )
    if query_date < start:
        return (
            JurisprudencePublicationTemporalState.PUBLISHED_AFTER_QUERY_DATE,
            False,
            False,
            ["publication_after_query_date"],
        )
    if query_date >= end or precision is JurisprudencePublicationDatePrecision.DAY:
        return (
            JurisprudencePublicationTemporalState.PUBLISHED_BY_QUERY_DATE,
            True,
            True,
            ["publication_available_by_query_date"],
        )
    return (
        JurisprudencePublicationTemporalState.AMBIGUOUS_AT_QUERY_DATE,
        None,
        False,
        ["publication_precision_insufficient_for_query_date"],
    )


def _binding_assessment(
    record: JurisprudenceTemporalRecord,
    query_date: date,
) -> tuple[JurisprudenceBindingTemporalState, bool | None, bool, list[str]]:
    if not record.binding_character_mandatory:
        return (
            JurisprudenceBindingTemporalState.NOT_JURISPRUDENCE,
            False,
            True,
            ["official_type_is_not_jurisprudence"],
        )

    start = record.parsed_binding_start
    end = record.parsed_binding_end
    precision = record.binding_date_precision
    if start is None or end is None:
        return (
            JurisprudenceBindingTemporalState.MANDATORY_DATE_UNKNOWN,
            None,
            True,
            ["jurisprudence_is_mandatory_but_effective_date_is_unknown"],
        )
    if query_date < start:
        return (
            JurisprudenceBindingTemporalState.MANDATORY_AFTER_QUERY_DATE,
            False,
            False,
            ["mandatory_effect_starts_after_query_date"],
        )
    if query_date >= end or precision is JurisprudencePublicationDatePrecision.DAY:
        return (
            JurisprudenceBindingTemporalState.MANDATORY_BY_QUERY_DATE,
            True,
            True,
            ["mandatory_effect_available_by_query_date"],
        )
    return (
        JurisprudenceBindingTemporalState.MANDATORY_DATE_AMBIGUOUS,
        None,
        False,
        ["mandatory_effective_date_precision_insufficient"],
    )


def assess_jurisprudence_temporal_context(
    record: JurisprudenceTemporalRecord,
    *,
    query_date: date,
) -> JurisprudenceTemporalAssessment:
    """E.4 separa publicación, obligatoriedad temporal y aplicabilidad material."""

    publication_state, published, publication_eligible, publication_reasons = (
        _publication_assessment(record, query_date)
    )
    binding_state, mandatory_by_date, binding_eligible, binding_reasons = (
        _binding_assessment(record, query_date)
    )

    reasons = [*publication_reasons, *binding_reasons]
    review = published is None or mandatory_by_date is None

    if record.binding_character_mandatory:
        eligible = publication_eligible and binding_eligible
    else:
        eligible = publication_eligible

    if record.criterion_status_claim in {
        JurisprudenceStatus.SUPERSEDED,
        JurisprudenceStatus.INVALIDATED,
        JurisprudenceStatus.HISTORICAL,
    }:
        review = True
        reasons.append(f"unverified_status_claim_{record.criterion_status_claim.value}")

    if not record.publication_date_verified:
        review = True
        reasons.append("publication_date_not_legally_verified")

    return JurisprudenceTemporalAssessment(
        document_id=record.document_id,
        query_date=query_date,
        publication_state=publication_state,
        published_by_query_date=published,
        binding_state=binding_state,
        binding_character_mandatory=record.binding_character_mandatory,
        mandatory_by_query_date=mandatory_by_date,
        temporally_eligible_for_evidence=eligible,
        criterion_status_claim=record.criterion_status_claim,
        requires_human_review=review,
        reasons=list(dict.fromkeys(reasons)),
    )
