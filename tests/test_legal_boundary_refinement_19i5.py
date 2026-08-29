from __future__ import annotations

from pathlib import Path

from app.domain.chunks import (
    ChunkMetadata,
    LegalChunk,
    LegalChunkType,
    LegalHierarchy,
)
from app.domain.documents import SourceType
from app.services.legal_boundary_refinement import (
    BoundaryRefinementClass,
    audit_boundary_refinement,
    find_article_headings,
    refine_boundary_cause,
    run_boundary_refinement,
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


def test_heading_detector_requires_line_anchored_legal_heading() -> None:
    text = (
        "Conforme al artículo 5 de esta Ley se procederá.\n"
        "Artículo 6.- Nuevo precepto."
    )
    headings = find_article_headings(text)
    assert [heading.identifier for heading in headings] == ["6"]


def test_true_secondary_boundary_requires_heading_in_parent() -> None:
    parent = _chunk(
        chunk_id="parent-0001",
        text=(
            "Artículo 1o.- Texto del primero.\n"
            "Artículo 2-C.- Texto del artículo siguiente."
        ),
    )
    child = _chunk(
        chunk_id="child-0001",
        text="Artículo 2-C.- Texto del artículo siguiente.",
        parent_chunk_id="parent-0001",
        sub_index=1,
        sub_count=2,
    )

    finding = refine_boundary_cause(child, parent)
    assert (
        finding.refinement_class
        == BoundaryRefinementClass.TRUE_SECONDARY_ARTICLE_BOUNDARY.value
    )
    assert finding.first_strong_heading == "2-c"


def test_cross_reference_is_not_promoted_to_legal_boundary() -> None:
    parent = _chunk(
        chunk_id="parent-0001",
        text=(
            "Artículo 1o.- Texto principal. Conforme al artículo 5 de esta Ley "
            "se aplicará el procedimiento."
        ),
    )
    child = _chunk(
        chunk_id="child-0001",
        text="Conforme al artículo 5 de esta Ley se aplicará el procedimiento.",
        parent_chunk_id="parent-0001",
        sub_index=1,
        sub_count=2,
    )

    finding = refine_boundary_cause(child, parent)
    assert (
        finding.refinement_class
        == BoundaryRefinementClass.CROSS_REFERENCE_FALSE_POSITIVE.value
    )
    assert finding.first_strong_heading is None


def test_parent_start_mismatch_remains_separate() -> None:
    parent = _chunk(
        chunk_id="parent-0018",
        text="Artículo 18-D.- Texto que fue etiquetado como artículo 18.",
        unit="Artículo 18",
    )
    child = _chunk(
        chunk_id="child-0018",
        text="Artículo 18-D.- Texto.",
        unit="Artículo 18",
        parent_chunk_id="parent-0018",
        sub_index=0,
        sub_count=1,
    )

    finding = refine_boundary_cause(child, parent)
    assert (
        finding.refinement_class
        == BoundaryRefinementClass.CANONICAL_PARENT_START_MISMATCH.value
    )


def test_line_start_reference_without_heading_separator_is_false_positive() -> None:
    parent = _chunk(
        chunk_id="parent-0001",
        text=(
            "Artículo 1o.- Texto.\n"
            "Artículo 5 de esta Ley será aplicable cuando corresponda."
        ),
    )
    child = _chunk(
        chunk_id="child-0001",
        text="Artículo 5 de esta Ley será aplicable cuando corresponda.",
        parent_chunk_id="parent-0001",
        sub_index=1,
        sub_count=2,
    )

    finding = refine_boundary_cause(child, parent)
    assert (
        finding.refinement_class
        == BoundaryRefinementClass.CROSS_REFERENCE_FALSE_POSITIVE.value
    )


def test_non_article_rule_is_preserved_as_non_article() -> None:
    parent = _chunk(
        chunk_id="parent-rmf-1",
        text="Regla 2.1.1. Texto administrativo.",
        unit="Regla 2.1.1",
        source_unit_type="rule",
        document_id="rmf_2026",
    )
    child = _chunk(
        chunk_id="child-rmf-1",
        text="Regla 2.1.1. Texto administrativo.",
        unit="Regla 2.1.1",
        source_unit_type="rule",
        document_id="rmf_2026",
        parent_chunk_id="parent-rmf-1",
        sub_index=0,
        sub_count=1,
    )

    finding = refine_boundary_cause(child, parent)
    assert finding.refinement_class == BoundaryRefinementClass.NON_ARTICLE_UNIT.value


def test_audit_counts_refined_classes() -> None:
    parent = _chunk(
        chunk_id="parent-0001",
        text=(
            "Artículo 1o.- Texto principal.\n"
            "Artículo 2-C.- Segundo artículo."
        ),
    )
    children = [
        _chunk(
            chunk_id="child-0001",
            text="Artículo 1o.- Texto principal.",
            parent_chunk_id="parent-0001",
            sub_index=0,
            sub_count=2,
        ),
        _chunk(
            chunk_id="child-0002",
            text="Artículo 2-C.- Segundo artículo.",
            parent_chunk_id="parent-0001",
            sub_index=1,
            sub_count=2,
        ),
    ]

    findings, summary = audit_boundary_refinement(
        retrieval_chunks=children,
        canonical_chunks=[parent],
    )
    assert len(findings) == 2
    counts = summary["refinement_counts"]
    assert isinstance(counts, dict)
    assert counts[BoundaryRefinementClass.RETRIEVAL_MATCH.value] == 1
    assert (
        counts[BoundaryRefinementClass.TRUE_SECONDARY_ARTICLE_BOUNDARY.value]
        == 1
    )


def test_run_refinement_writes_separate_queues(tmp_path: Path) -> None:
    canonical_path = tmp_path / "canonical.jsonl"
    retrieval_path = tmp_path / "retrieval.jsonl"

    parent = _chunk(
        chunk_id="parent-0001",
        text=(
            "Artículo 1o.- Texto principal.\n"
            "Artículo 2-C.- Segundo artículo."
        ),
    )
    child = _chunk(
        chunk_id="child-0001",
        text="Artículo 2-C.- Segundo artículo.",
        parent_chunk_id="parent-0001",
        sub_index=1,
        sub_count=2,
    )

    canonical_path.write_text(parent.model_dump_json() + "\n", encoding="utf-8")
    retrieval_path.write_text(child.model_dump_json() + "\n", encoding="utf-8")

    findings, summary, outputs = run_boundary_refinement(
        retrieval_path=retrieval_path,
        canonical_path=canonical_path,
        output_dir=tmp_path / "out",
    )

    assert len(findings) == 1
    assert summary["canonical_chunks"] == 1
    assert all(path.exists() for path in outputs.values())
    boundary_lines = outputs["true_boundaries"].read_text(
        encoding="utf-8"
    ).splitlines()
    assert len([line for line in boundary_lines if line]) == 1


def test_heading_detector_accepts_markdown_heading_prefix() -> None:
    headings = find_article_headings("### Artículo 31.- Texto legal.")
    assert [heading.identifier for heading in headings] == ["31"]


def test_heading_detector_does_not_backtrack_hyphenated_reference() -> None:
    headings = find_article_headings(
        "artículo 31-A, primer párrafo.\n### Artículo 31.- Texto."
    )
    assert [heading.identifier for heading in headings] == ["31"]
