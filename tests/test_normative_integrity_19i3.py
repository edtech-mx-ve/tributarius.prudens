from __future__ import annotations

import json
from pathlib import Path

from app.domain.chunks import (
    ChunkMetadata,
    LegalChunk,
    LegalChunkType,
    LegalHierarchy,
)
from app.domain.documents import SourceType
from app.services.legal_unit_integrity import (
    ArticleConsistency,
    compare_article_unit,
    extract_article_identifier,
)
from app.services.normative_integrity_audit import (
    analyze_normative_chunk,
    audit_normative_chunks,
    classify_temporal_status,
    run_audit,
)


def _chunk(
    *,
    chunk_id: str = "chunk-liva-0001",
    document_id: str = "liva",
    source_type: SourceType = SourceType.NORMATIVA,
    unit: str | None = "Artículo 1o",
    text: str = "Artículo 1o. Se aplicará la tasa prevista por la ley.",
    effective_from: str | None = "2026-01-01",
    effective_to: str | None = None,
    version_label: str | None = "2026-01-01",
) -> LegalChunk:
    return LegalChunk(
        chunk_id=chunk_id,
        text=text,
        metadata=ChunkMetadata(
            document_id=document_id,
            source_type=source_type,
            source_filename=f"{document_id}.md",
            chunk_index=0,
            chunk_type=LegalChunkType.ARTICLE,
            legal_identifier=unit,
            source_unit_label=unit,
            hierarchy=LegalHierarchy(article=unit),
            source_sha256="a" * 64,
            version_label=version_label,
            effective_from=effective_from,
            effective_to=effective_to,
        ),
    )


def test_article_parser_handles_1o_and_hyphenated_identifiers() -> None:
    assert extract_article_identifier("Artículo 1o.") == "1o"
    assert extract_article_identifier("ARTICULO 2-C.") == "2-c"
    assert extract_article_identifier("Artículo 2o-A.") == "2o-a"


def test_article_consistency_classifies_match_mismatch_and_unverifiable() -> None:
    assert (
        compare_article_unit("Artículo 1o", "Artículo 1o. Texto")
        == ArticleConsistency.MATCH
    )
    assert (
        compare_article_unit("Artículo 1o", "Artículo 2-C. Texto")
        == ArticleConsistency.MISMATCH
    )
    assert (
        compare_article_unit("Artículo 1o", "Continuación del párrafo anterior.")
        == ArticleConsistency.TEXT_WITHOUT_ARTICLE
    )
    assert (
        compare_article_unit("Capítulo I", "Artículo 1o. Texto")
        == ArticleConsistency.METADATA_WITHOUT_ARTICLE
    )


def test_temporal_status_does_not_infer_from_reform_or_publication() -> None:
    chunk = _chunk(effective_from=None, effective_to=None)
    chunk.metadata.last_reform_date = "2021-11-12"
    chunk.metadata.publication_date = "1978-12-29"
    assert classify_temporal_status(chunk) == "unknown"


def test_temporal_status_rejects_invalid_and_reversed_ranges() -> None:
    assert classify_temporal_status(_chunk(effective_from="no-date")) == "invalid"
    assert (
        classify_temporal_status(
            _chunk(effective_from="2026-12-31", effective_to="2026-01-01")
        )
        == "invalid"
    )


def test_analysis_marks_mismatch_as_not_promotable() -> None:
    finding = analyze_normative_chunk(
        _chunk(text="Artículo 2-C. Texto de otra unidad.")
    )
    assert finding.article_consistency == "mismatch"
    assert finding.promotion_eligible is False


def test_analysis_keeps_unknown_temporal_metadata_out_of_promotion() -> None:
    finding = analyze_normative_chunk(
        _chunk(effective_from=None, effective_to=None)
    )
    assert finding.temporal_status == "unknown"
    assert finding.promotion_eligible is False


def test_audit_only_counts_normative_chunks_and_groups_documents() -> None:
    chunks = [
        _chunk(chunk_id="norm-0001"),
        _chunk(
            chunk_id="norm-0002",
            text="Artículo 2-C. Contradicción.",
        ),
        _chunk(
            chunk_id="support-0001",
            document_id="unam",
            source_type=SourceType.UNAM,
        ),
    ]
    findings, summary = audit_normative_chunks(chunks)
    assert len(findings) == 2
    assert summary["total_chunks"] == 3
    assert summary["normative_chunks"] == 2
    assert summary["normative_documents"] == 1
    assert summary["article_match"] == 1
    assert summary["article_mismatch"] == 1


def test_run_audit_writes_report_csv_quarantine_and_temporal_backlog(
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "chunks.jsonl"
    rows = [
        _chunk(chunk_id="norm-0001"),
        _chunk(
            chunk_id="norm-0002",
            text="Artículo 2-C. Contradicción.",
        ),
        _chunk(
            chunk_id="norm-0003",
            effective_from=None,
            effective_to=None,
        ),
    ]
    input_path.write_text(
        "\n".join(chunk.model_dump_json() for chunk in rows) + "\n",
        encoding="utf-8",
    )

    findings, summary, outputs = run_audit(
        input_path=input_path,
        output_dir=tmp_path / "report",
    )

    assert len(findings) == 3
    assert summary["article_mismatch"] == 1
    assert summary["temporal_unknown"] == 1
    assert all(path.exists() for path in outputs.values())

    report = json.loads(outputs["report"].read_text(encoding="utf-8"))
    assert report["policy"]["mutates_corpus"] is False
    assert report["policy"]["last_reform_is_not_effective_from"] is True

    quarantine_lines = [
        line
        for line in outputs["quarantine"].read_text(encoding="utf-8").splitlines()
        if line
    ]
    temporal_lines = [
        line
        for line in outputs["temporal_backlog"].read_text(
            encoding="utf-8"
        ).splitlines()
        if line
    ]
    assert len(quarantine_lines) == 1
    assert len(temporal_lines) == 1


def test_audit_counts_text_without_article_without_keyerror() -> None:
    chunk = _chunk(
        chunk_id="norm-no-explicit-article",
        unit="Artículo 1o",
        text="Continuación del contenido normativo sin encabezado explícito.",
    )
    findings, summary = audit_normative_chunks([chunk])
    assert len(findings) == 1
    assert findings[0].article_consistency == "text_without_article"
    assert summary["text_without_article"] == 1
    assert summary["article_match"] == 0
    assert summary["article_mismatch"] == 0


def test_audit_script_summary_int_rejects_non_integer_values() -> None:
    from app.services.normative_integrity_audit import NormativeIntegrityAuditError
    from scripts.audit_normative_integrity import _summary_int

    assert _summary_int({"total_chunks": 29402}, "total_chunks") == 29402

    try:
        _summary_int({"total_chunks": "29402"}, "total_chunks")
    except NormativeIntegrityAuditError:
        pass
    else:
        raise AssertionError("Se esperaba NormativeIntegrityAuditError")
