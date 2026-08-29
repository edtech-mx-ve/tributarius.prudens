from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from app.services.semantic_runtime_rebuild import (
    SemanticRuntimeRebuildError,
    validate_semantic_runtime_inputs,
)


def _chunk_json(index: int) -> str:
    payload = {
        'chunk_id': f'doc:article:articulo-{index}:{index:05d}:abcdef1234567890',
        'canonical_id': 'doc',
        'source_role': 'normativa',
        'document_type': 'ley',
        'title': 'Documento',
        'unit_type': 'article',
        'unit_label': f'Artículo {index}',
        'hierarchy': [],
        'page_start': 1,
        'page_end': 1,
        'fiscal_year': None,
        'source_sha256': 'a' * 64,
        'text_sha256': hashlib.sha256(f'Artículo {index}. Texto.'.encode()).hexdigest(),
        'text': f'Artículo {index}. Texto.',
        'matter': [],
        'jurisdiction': 'México',
        'publication_date': None,
        'last_reform_date': None,
        'effective_from': None,
        'effective_to': None,
    }
    return json.dumps(payload, ensure_ascii=False)


def test_validate_semantic_runtime_inputs_accepts_matching_manifest(tmp_path: Path) -> None:
    corpus = tmp_path / 'chunks.jsonl'
    corpus.write_text(_chunk_json(1) + '\n', encoding='utf-8')
    digest = hashlib.sha256(corpus.read_bytes()).hexdigest()
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(
        json.dumps(
            {
                'status': 'approved_semantic_canonical',
                'promoted_chunks': 1,
                'promoted_sha256': digest,
            }
        ),
        encoding='utf-8',
    )

    result = validate_semantic_runtime_inputs(
        canonical_path=corpus,
        manifest_path=manifest,
        expected_parent_count=1,
    )
    assert result.expected_parent_count == 1
    assert result.canonical_sha256 == digest


def test_validate_semantic_runtime_inputs_rejects_hash_mismatch(tmp_path: Path) -> None:
    corpus = tmp_path / 'chunks.jsonl'
    corpus.write_text(_chunk_json(1) + '\n', encoding='utf-8')
    manifest = tmp_path / 'manifest.json'
    manifest.write_text(
        json.dumps(
            {
                'status': 'approved_semantic_canonical',
                'promoted_chunks': 1,
                'promoted_sha256': '0' * 64,
            }
        ),
        encoding='utf-8',
    )

    with pytest.raises(SemanticRuntimeRebuildError):
        validate_semantic_runtime_inputs(
            canonical_path=corpus,
            manifest_path=manifest,
            expected_parent_count=1,
        )
