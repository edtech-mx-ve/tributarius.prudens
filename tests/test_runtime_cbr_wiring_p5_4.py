from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.runtime_factory import (
    RuntimeBuildError,
    load_runtime_cbr_cases,
)

PRODUCTION_CBR = "cbr/data/production_cases.jsonl"


def test_runtime_default_points_to_production_cbr_corpus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "RUNTIME_CBR_CASES_PATH",
        raising=False,
    )

    settings = Settings(_env_file=None)

    assert settings.runtime_cbr_cases_path == PRODUCTION_CBR


def test_runtime_loads_two_production_cbr_cases() -> None:
    settings = Settings(
        _env_file=None,
        runtime_cbr_cases_path=PRODUCTION_CBR,
    )

    cases = load_runtime_cbr_cases(settings)

    assert len(cases) == 2
    assert {
        case.case_id
        for case in cases
    } == {
        "CASE-TP-ISR-PROF-CUMPL-2026",
        "CASE-TP-ISR-PROF-DETERM-2026",
    }


def test_runtime_rejects_missing_cbr_corpus() -> None:
    settings = Settings(
        _env_file=None,
        runtime_cbr_cases_path="cbr/data/missing.jsonl",
    )

    with pytest.raises(
        RuntimeBuildError,
        match="corpus CBR productivo",
    ):
        load_runtime_cbr_cases(settings)


def test_runtime_factory_wires_cases_into_orchestrator() -> None:
    source = Path(
        "app/services/runtime_factory.py"
    ).read_text(encoding="utf-8")

    assert "cbr_cases = load_runtime_cbr_cases(settings)" in source
    assert "cbr_cases=cbr_cases" in source
