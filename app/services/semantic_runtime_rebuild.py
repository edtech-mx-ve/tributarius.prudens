from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from app.domain.legal_chunks import LegalChunk


class SemanticRuntimeRebuildError(RuntimeError):
    """Fallo controlado al preparar artefactos RAG del corpus semántico."""


@dataclass(frozen=True)
class SemanticRuntimeInputs:
    canonical_path: Path
    manifest_path: Path
    expected_parent_count: int
    canonical_sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def _count_valid_chunks(path: Path) -> int:
    count = 0
    try:
        with path.open('r', encoding='utf-8') as handle:
            for line_number, raw in enumerate(handle, start=1):
                if not raw.strip():
                    continue
                try:
                    LegalChunk.model_validate_json(raw)
                except ValueError as exc:
                    raise SemanticRuntimeRebuildError(
                        f'Chunk inválido en {path}:{line_number}'
                    ) from exc
                count += 1
    except OSError as exc:
        raise SemanticRuntimeRebuildError(f'No se pudo leer {path}') from exc
    return count


def validate_semantic_runtime_inputs(
    *,
    canonical_path: Path,
    manifest_path: Path,
    expected_parent_count: int = 2981,
) -> SemanticRuntimeInputs:
    canonical = canonical_path.expanduser().resolve()
    manifest = manifest_path.expanduser().resolve()
    if not canonical.is_file():
        raise SemanticRuntimeRebuildError(f'No existe corpus promovido: {canonical}')
    if not manifest.is_file():
        raise SemanticRuntimeRebuildError(f'No existe manifiesto promovido: {manifest}')

    try:
        payload = json.loads(manifest.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        raise SemanticRuntimeRebuildError(f'Manifiesto inválido: {manifest}') from exc

    if payload.get('status') != 'approved_semantic_canonical':
        raise SemanticRuntimeRebuildError(
            'El corpus no está marcado como approved_semantic_canonical.'
        )
    manifest_count = payload.get('promoted_chunks')
    if manifest_count != expected_parent_count:
        raise SemanticRuntimeRebuildError(
            f'promoted_chunks={manifest_count}; esperado={expected_parent_count}'
        )

    real_count = _count_valid_chunks(canonical)
    if real_count != expected_parent_count:
        raise SemanticRuntimeRebuildError(
            f'Corpus contiene {real_count} chunks; esperado={expected_parent_count}'
        )

    real_sha = _sha256(canonical)
    manifest_sha = str(payload.get('promoted_sha256', ''))
    if real_sha != manifest_sha:
        raise SemanticRuntimeRebuildError(
            'SHA-256 del corpus promovido no coincide con su manifiesto.'
        )

    return SemanticRuntimeInputs(
        canonical_path=canonical,
        manifest_path=manifest,
        expected_parent_count=expected_parent_count,
        canonical_sha256=real_sha,
    )
