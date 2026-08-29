from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.public_safe_runtime_19i18k import (
    EXPECTED_NORMATIVE_DOCUMENTS,
    PublicSafeRuntimeError,
    build_normative_eval_cases,
    build_normative_only_canonical,
)


def _chunk(document_id: str, index: int) -> str:
    return json.dumps(
        {
            "document_id": document_id,
            "chunk_id": f"{document_id}-{index}",
            "text": document_id,
        }
    )


def test_normative_filter_excludes_only_doctrine_layers(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    rows = [
        _chunk(document_id, index)
        for index, document_id in enumerate(
            sorted(EXPECTED_NORMATIVE_DOCUMENTS)
            + ["manual_unam", "prodecon"],
            start=1,
        )
    ]
    source.write_text("\n".join(rows) + "\n", encoding="utf-8")
    target = tmp_path / "public.jsonl"

    result = build_normative_only_canonical(source, target)

    assert result.document_ids == sorted(EXPECTED_NORMATIVE_DOCUMENTS)
    assert result.blocked_removed == ["manual_unam", "prodecon"]
    assert result.parent_count == 14
    text = target.read_text(encoding="utf-8")
    assert "manual_unam" not in text
    assert "prodecon" not in text


def test_unknown_document_fails_closed(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    rows = [
        _chunk(document_id, index)
        for index, document_id in enumerate(
            sorted(EXPECTED_NORMATIVE_DOCUMENTS)
            + ["manual_unam", "prodecon", "mystery"],
            start=1,
        )
    ]
    source.write_text("\n".join(rows) + "\n", encoding="utf-8")
    with pytest.raises(PublicSafeRuntimeError):
        build_normative_only_canonical(source, tmp_path / "public.jsonl")


def test_normative_cases_drop_blocked_expected_documents(tmp_path: Path) -> None:
    source = tmp_path / "cases.json"
    source.write_text(
        json.dumps(
            {
                "cases": [
                    {"id": "a", "expected_document_id": "cff"},
                    {"id": "b", "expected_document_id": "prodecon"},
                    {"id": "c", "expected_document_id": "lisr"},
                ]
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "filtered.json"
    count = build_normative_eval_cases(source, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert count == 2
    assert [row["id"] for row in payload["cases"]] == ["a", "c"]


def test_eval_cases_without_recognized_documents_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "cases.json"
    source.write_text(json.dumps({"cases": [{"id": "x"}]}), encoding="utf-8")
    with pytest.raises(PublicSafeRuntimeError):
        build_normative_eval_cases(source, tmp_path / "filtered.json")
