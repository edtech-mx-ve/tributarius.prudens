from __future__ import annotations

from pathlib import Path

import pytest

from app.domain.chunks import (
    ChunkMetadata,
    LegalChunk,
    LegalChunkType,
    LegalHierarchy,
)
from app.domain.documents import SourceType
from app.services.canonical_prefix_repair import (
    analyze_prefix_repair,
    apply_prefix_repair,
)
from app.services.normative_integrity_audit import NormativeIntegrityAuditError
from rag.indexing.builder import load_chunks_jsonl


def _chunk(
    *,
    chunk_id: str,
    text: str,
    unit: str = "Artículo 31",
    document_id: str = "cff",
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
        source_unit_type="article",
        source_unit_label=unit,
        version_label="2026-04-09",
    )
    return LegalChunk(chunk_id=chunk_id, text=text, metadata=metadata)


def test_prefix_before_matching_heading_is_repairable() -> None:
    chunk = _chunk(
        chunk_id="cff-0031",
        text=(
            "artículo 31-A, primer párrafo, inciso d) de este Código.\n"
            "### Artículo 31.- Las personas deberán presentar..."
        ),
    )
    finding = analyze_prefix_repair(chunk)
    assert finding.repairable is True
    assert finding.metadata_article == "31"
    assert finding.first_heading_article == "31"
    assert finding.prefix_chars > 0


def test_aligned_markdown_heading_is_not_repaired() -> None:
    chunk = _chunk(
        chunk_id="cff-0031",
        text="### Artículo 31.- Las personas deberán presentar...",
    )
    finding = analyze_prefix_repair(chunk)
    assert finding.repairable is False
    assert finding.reason == "already_aligned"


def test_hyphenated_reference_is_not_misread_as_heading() -> None:
    chunk = _chunk(
        chunk_id="cff-0031",
        text=(
            "artículo 31-A, primer párrafo, inciso d) de este Código.\n"
            "### Artículo 31.- Texto correcto."
        ),
    )
    finding = analyze_prefix_repair(chunk)
    assert finding.first_heading_article == "31"
    assert finding.repairable is True


def test_different_first_heading_is_fail_closed() -> None:
    chunk = _chunk(
        chunk_id="cff-0031",
        text="### Artículo 31-A.- Texto de otro artículo.",
    )
    finding = analyze_prefix_repair(chunk)
    assert finding.repairable is False
    assert finding.reason == "first_heading_does_not_match_metadata"


def test_apply_writes_new_copy_and_preserves_cardinality(tmp_path: Path) -> None:
    input_path = tmp_path / "chunks.jsonl"
    output_path = tmp_path / "repaired.jsonl"
    contaminated = _chunk(
        chunk_id="cff-0031",
        text=(
            "artículo 31-A, primer párrafo, inciso d) de este Código.\n"
            "### Artículo 31.- Las personas deberán presentar..."
        ),
    )
    unaffected = _chunk(
        chunk_id="cff-0032",
        text="### Artículo 32.- Texto correcto.",
        unit="Artículo 32",
    )
    input_path.write_text(
        contaminated.model_dump_json()
        + "\n"
        + unaffected.model_dump_json()
        + "\n",
        encoding="utf-8",
    )

    plan = apply_prefix_repair(
        input_path=input_path,
        output_path=output_path,
        candidate_chunk_ids=["cff-0031"],
    )

    assert len(plan.findings) == 1
    repaired = load_chunks_jsonl(output_path)
    assert len(repaired) == 2
    assert repaired[0].text.startswith("### Artículo 31.-")
    assert repaired[1].text == unaffected.text
    assert input_path.read_text(encoding="utf-8").startswith(
        contaminated.model_dump_json()
    )


def test_apply_refuses_to_overwrite_input(tmp_path: Path) -> None:
    input_path = tmp_path / "chunks.jsonl"
    chunk = _chunk(
        chunk_id="cff-0031",
        text="prefijo\n### Artículo 31.- Texto.",
    )
    input_path.write_text(chunk.model_dump_json() + "\n", encoding="utf-8")

    with pytest.raises(NormativeIntegrityAuditError):
        apply_prefix_repair(
            input_path=input_path,
            output_path=input_path,
            candidate_chunk_ids=["cff-0031"],
        )


def test_apply_refuses_existing_output(tmp_path: Path) -> None:
    input_path = tmp_path / "chunks.jsonl"
    output_path = tmp_path / "repaired.jsonl"
    chunk = _chunk(
        chunk_id="cff-0031",
        text="prefijo\n### Artículo 31.- Texto.",
    )
    input_path.write_text(chunk.model_dump_json() + "\n", encoding="utf-8")
    output_path.write_text("sentinel", encoding="utf-8")

    with pytest.raises(NormativeIntegrityAuditError):
        apply_prefix_repair(
            input_path=input_path,
            output_path=output_path,
            candidate_chunk_ids=["cff-0031"],
        )

    assert output_path.read_text(encoding="utf-8") == "sentinel"
