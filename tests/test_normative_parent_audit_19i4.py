from __future__ import annotations

from pathlib import Path

from app.domain.chunks import (
    ChunkMetadata,
    LegalChunk,
    LegalChunkType,
    LegalHierarchy,
)
from app.domain.documents import SourceType
from app.services.normative_parent_audit import (
    CausalClass,
    audit_parent_integrity,
    classify_cause,
    run_parent_audit,
)


def _chunk(
    *,
    chunk_id: str,
    text: str,
    unit: str | None = "Artículo 1o",
    source_unit_type: str | None = "article",
    parent_chunk_id: str | None = None,
    sub_index: int | None = None,
    sub_count: int | None = None,
    document_id: str = "liva",
) -> LegalChunk:
    metadata = ChunkMetadata(
        document_id=document_id,
        source_type=SourceType.NORMATIVA,
        source_filename=f"{document_id}.md",
        chunk_index=0,
        chunk_type=LegalChunkType.ARTICLE,
        legal_identifier=unit,
        hierarchy=LegalHierarchy(article=unit),
        source_sha256="a" * 64,
        source_unit_type=source_unit_type,
        source_unit_label=unit,
        version_label="2021-11-12",
        parent_chunk_id=parent_chunk_id,
        retrieval_subchunk_index=sub_index,
        retrieval_subchunk_count=sub_count,
    )
    return LegalChunk(chunk_id=chunk_id, text=text, metadata=metadata)


def test_canonical_parent_mismatch_is_classified_as_19c_defect() -> None:
    parent = _chunk(
        chunk_id="parent-0001",
        text="Artículo 2-C. Texto incorrectamente etiquetado.",
    )
    child = _chunk(
        chunk_id="child-0001",
        text="Artículo 2-C. Subchunk.",
        parent_chunk_id="parent-0001",
        sub_index=0,
        sub_count=1,
    )
    finding = classify_cause(child, parent)
    assert finding.causal_class == CausalClass.CANONICAL_PARENT_MISMATCH.value


def test_retrieval_mismatch_with_verified_parent_is_19f_drift() -> None:
    parent = _chunk(
        chunk_id="parent-0001",
        text="Artículo 1o. Padre correcto. Artículo 2-C. Texto posterior.",
    )
    child = _chunk(
        chunk_id="child-0001",
        text="Artículo 2-C. Texto posterior.",
        parent_chunk_id="parent-0001",
        sub_index=1,
        sub_count=2,
    )
    finding = classify_cause(child, parent)
    assert (
        finding.causal_class
        == CausalClass.RETRIEVAL_MISMATCH_PARENT_VERIFIED.value
    )


def test_continuation_with_verified_parent_is_not_mismatch() -> None:
    parent = _chunk(
        chunk_id="parent-0001",
        text="Artículo 1o. Padre correcto.",
    )
    child = _chunk(
        chunk_id="child-0001",
        text="Continuación del artículo sin encabezado explícito.",
        parent_chunk_id="parent-0001",
        sub_index=1,
        sub_count=2,
    )
    finding = classify_cause(child, parent)
    assert (
        finding.causal_class
        == CausalClass.RETRIEVAL_CONTINUATION_PARENT_VERIFIED.value
    )


def test_non_article_unit_does_not_become_article_failure() -> None:
    parent = _chunk(
        chunk_id="parent-rmf-0001",
        text="Regla 2.1.1. Texto administrativo.",
        unit="Regla 2.1.1",
        source_unit_type="rule",
        document_id="rmf_2026",
    )
    child = _chunk(
        chunk_id="child-rmf-0001",
        text="Regla 2.1.1. Texto administrativo.",
        unit="Regla 2.1.1",
        source_unit_type="rule",
        document_id="rmf_2026",
        parent_chunk_id="parent-rmf-0001",
        sub_index=0,
        sub_count=1,
    )
    finding = classify_cause(child, parent)
    assert finding.causal_class == CausalClass.NON_ARTICLE_UNIT.value


def test_audit_groups_causal_counts() -> None:
    parents = [
        _chunk(
            chunk_id="parent-0001",
            text="Artículo 1o. Padre correcto. Artículo 2-C. Posterior.",
        )
    ]
    children = [
        _chunk(
            chunk_id="child-0001",
            text="Artículo 1o. Inicio.",
            parent_chunk_id="parent-0001",
            sub_index=0,
            sub_count=2,
        ),
        _chunk(
            chunk_id="child-0002",
            text="Artículo 2-C. Posterior.",
            parent_chunk_id="parent-0001",
            sub_index=1,
            sub_count=2,
        ),
    ]
    findings, summary = audit_parent_integrity(
        retrieval_chunks=children,
        canonical_chunks=parents,
    )
    assert len(findings) == 2
    assert summary["retrieval_chunks"] == 2
    assert summary["canonical_chunks"] == 1
    counts = summary["causal_counts"]
    assert isinstance(counts, dict)
    assert counts[CausalClass.RETRIEVAL_MATCH.value] == 1
    assert counts[CausalClass.RETRIEVAL_MISMATCH_PARENT_VERIFIED.value] == 1


def test_run_parent_audit_writes_repair_queues(tmp_path: Path) -> None:
    canonical_path = tmp_path / "canonical.jsonl"
    retrieval_path = tmp_path / "retrieval.jsonl"

    parent = _chunk(
        chunk_id="parent-0001",
        text="Artículo 1o. Padre correcto. Artículo 2-C. Posterior.",
    )
    child = _chunk(
        chunk_id="child-0001",
        text="Artículo 2-C. Posterior.",
        parent_chunk_id="parent-0001",
        sub_index=1,
        sub_count=2,
    )

    canonical_path.write_text(
        parent.model_dump_json() + "\n",
        encoding="utf-8",
    )
    retrieval_path.write_text(
        child.model_dump_json() + "\n",
        encoding="utf-8",
    )

    findings, summary, outputs = run_parent_audit(
        retrieval_path=retrieval_path,
        canonical_path=canonical_path,
        output_dir=tmp_path / "out",
    )

    assert len(findings) == 1
    assert summary["canonical_chunks"] == 1
    assert all(path.exists() for path in outputs.values())
    repair_lines = outputs["repair_19f"].read_text(
        encoding="utf-8"
    ).splitlines()
    assert len([line for line in repair_lines if line]) == 1
