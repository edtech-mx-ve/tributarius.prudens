import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.jurisprudence import (
    JurisprudenceCriterionType,
    JurisprudenceMetadata,
    JurisprudenceStatus,
    NormRelationType,
)
from jurisprudence.assessment import assess_jurisprudential_candidate
from jurisprudence.loader import JurisprudenceMetadataError, load_jurisprudence_metadata


def metadata(
    *,
    status: JurisprudenceStatus = JurisprudenceStatus.CURRENT,
    verified: bool = True,
    publication_date: date = date(2026, 1, 15),
    related_refs: list[str] | None = None,
    relation: NormRelationType = NormRelationType.INTERPRETS,
) -> JurisprudenceMetadata:
    return JurisprudenceMetadata(
        document_id="jur-test-001",
        identifier="SYN-JUR-001",
        title="Criterio sintético",
        court_or_body="Órgano sintético",
        criterion_type=JurisprudenceCriterionType.JURISPRUDENCE,
        publication_date=publication_date,
        status=status,
        matter="fiscal",
        source_reference="FIXTURE_ONLY",
        source_sha256="a" * 64,
        verified=verified,
        related_normative_refs=(
            ["NORM_TEST_ISR_2026"] if related_refs is None else related_refs
        ),
        relation_type=relation,
    )


def test_fixture_metadata_loads_without_persistence() -> None:
    records = load_jurisprudence_metadata(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    )
    assert len(records) == 3
    assert records["jur-test-current"].verified is True


def test_relation_requires_normative_reference() -> None:
    with pytest.raises(ValidationError):
        metadata(
            related_refs=[],
            relation=NormRelationType.INTERPRETS,
        )


def test_current_verified_candidate_is_eligible_and_related() -> None:
    result = assess_jurisprudential_candidate(
        metadata(),
        query_date=date(2026, 8, 28),
        applicable_normative_refs={"NORM_TEST_ISR_2026"},
        matter="fiscal",
    )
    assert result.eligible is True
    assert result.relevant_to_norm is True
    assert result.requires_human_review is False


def test_superseded_candidate_is_excluded() -> None:
    result = assess_jurisprudential_candidate(
        metadata(status=JurisprudenceStatus.SUPERSEDED),
        query_date=date(2026, 8, 28),
        applicable_normative_refs={"NORM_TEST_ISR_2026"},
    )
    assert result.eligible is False
    assert result.requires_human_review is True


def test_historical_candidate_requires_review() -> None:
    result = assess_jurisprudential_candidate(
        metadata(status=JurisprudenceStatus.HISTORICAL),
        query_date=date(2026, 8, 28),
        applicable_normative_refs={"NORM_TEST_ISR_2026"},
    )
    assert result.eligible is True
    assert result.requires_human_review is True


def test_future_publication_is_excluded() -> None:
    result = assess_jurisprudential_candidate(
        metadata(publication_date=date(2027, 1, 1)),
        query_date=date(2026, 8, 28),
        applicable_normative_refs={"NORM_TEST_ISR_2026"},
    )
    assert result.eligible is False


def test_unverified_metadata_is_excluded() -> None:
    result = assess_jurisprudential_candidate(
        metadata(verified=False),
        query_date=date(2026, 8, 28),
        applicable_normative_refs={"NORM_TEST_ISR_2026"},
    )
    assert result.eligible is False


def test_unrelated_norm_requires_review_but_does_not_claim_conflict() -> None:
    result = assess_jurisprudential_candidate(
        metadata(),
        query_date=date(2026, 8, 28),
        applicable_normative_refs={"OTHER_NORM"},
    )
    assert result.eligible is True
    assert result.relevant_to_norm is False
    assert result.requires_human_review is True
    assert "no_shared_normative_ref" in result.reasons


def test_loader_rejects_duplicate_ids(tmp_path: Path) -> None:
    source = Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
    first = source.read_text(encoding="utf-8").splitlines()[0]
    path = tmp_path / "duplicate.jsonl"
    path.write_text(first + "\n" + first + "\n", encoding="utf-8")
    with pytest.raises(JurisprudenceMetadataError):
        load_jurisprudence_metadata(path)


def test_loader_rejects_unknown_fields(tmp_path: Path) -> None:
    payload = json.loads(
        Path("jurisprudence/fixtures/metadata_synthetic.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    payload["unexpected"] = "value"
    path = tmp_path / "invalid.jsonl"
    path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    with pytest.raises(JurisprudenceMetadataError):
        load_jurisprudence_metadata(path)
