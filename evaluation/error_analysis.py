from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, Field

from evaluation.models import IntegralEvaluationReport


class ErrorBucket(BaseModel):
    code: str
    count: int = Field(ge=1)
    case_ids: list[str]


class ErrorAnalysis(BaseModel):
    failed_case_count: int = Field(ge=0)
    buckets: list[ErrorBucket]


def analyze_errors(report: IntegralEvaluationReport) -> ErrorAnalysis:
    buckets: dict[str, list[str]] = {}
    for case in report.cases:
        for failure in case.failures:
            code = failure.split("=", maxsplit=1)[0]
            buckets.setdefault(code, []).append(case.case_id)

    counts = Counter({code: len(case_ids) for code, case_ids in buckets.items()})
    ordered = sorted(counts, key=lambda code: (-counts[code], code))
    return ErrorAnalysis(
        failed_case_count=sum(not case.passed for case in report.cases),
        buckets=[
            ErrorBucket(
                code=code,
                count=counts[code],
                case_ids=sorted(buckets[code]),
            )
            for code in ordered
        ],
    )
