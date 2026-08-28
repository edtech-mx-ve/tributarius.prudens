import json
from pathlib import Path

from app.domain.traceability import (
    CanonicalExecutionResult,
    EvidenceKind,
    EvidenceReference,
)


def test_canonical_fixture_keeps_separate_jurisprudential_sources() -> None:
    payload = json.loads(
        Path("traceability/fixtures/trace_test.json").read_text(encoding="utf-8")
    )
    result = CanonicalExecutionResult.model_validate(payload)
    assert result.traceability.jurisprudential_sources == []


def test_jurisprudence_has_dedicated_evidence_kind() -> None:
    evidence = EvidenceReference(
        ref_id="SYN-JUR-001",
        kind=EvidenceKind.JURISPRUDENCE,
        source_type="jurisprudencia",
        source_reference="FIXTURE_ONLY",
    )
    assert evidence.kind == EvidenceKind.JURISPRUDENCE
