from pathlib import Path

import pytest

from app.services.cbr_loader import CBRLoadError, load_cbr_cases_jsonl


def test_load_cbr_fixture() -> None:
    cases = load_cbr_cases_jsonl(Path("cbr/fixtures/cases_test.jsonl"))
    assert len(cases) == 3


def test_reject_non_jsonl(tmp_path: Path) -> None:
    path = tmp_path / "cases.json"
    path.write_text("{}", encoding="utf-8")
    with pytest.raises(CBRLoadError):
        load_cbr_cases_jsonl(path)


def test_reject_duplicate_case_id(tmp_path: Path) -> None:
    path = tmp_path / "cases.jsonl"
    row = (
        '{"case_id":"CASE-001","status":"active",'
        '"taxpayer_type":"individual","activity":"servicios",'
        '"tax":"ISR","problem_type":"obligaciones",'
        '"fiscal_year":2026,"resolution_summary":"x","source_refs":["SRC"],'
        '"anonymized":true,"validated":true}'
    )
    path.write_text(row + "\n" + row + "\n", encoding="utf-8")
    with pytest.raises(CBRLoadError):
        load_cbr_cases_jsonl(path)
