from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.services.corpus_chunking_service import (
    CorpusChunkingError,
    build_legal_chunks,
)
from app.services.semantic_canonical_audit import (
    SemanticCanonicalAuditError,
    compare_canonical_corpora,
    write_semantic_report,
)
from app.services.semantic_corpus_promotion import (
    SemanticCorpusPromotionError,
    promote_semantic_corpus,
)

AUTHORIZED_DOCUMENTS = {"lfdc", "reg_liva_250914"}


class SelectiveSemanticCandidateError(RuntimeError):
    """Controlled error for the isolated semantic candidate build."""


@dataclass(frozen=True)
class SemanticDocumentDelta:
    document_id: str
    current_count: int
    candidate_count: int
    current_sha256: str
    candidate_sha256: str
    changed: bool


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectiveSemanticCandidateError(f"JSON inválido: {path}") from exc
    if not isinstance(value, dict):
        raise SelectiveSemanticCandidateError(f"Objeto JSON esperado: {path}")
    return value


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _relative_under(path_value: str, base: Path, label: str) -> Path:
    path = Path(path_value).expanduser()
    try:
        return path.resolve().relative_to(base.resolve())
    except ValueError as exc:
        raise SelectiveSemanticCandidateError(
            f"{label}: ruta fuera del árbol canónico esperado: {path}"
        ) from exc


def _require_string(row: dict[str, Any], key: str, document_id: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise SelectiveSemanticCandidateError(
            f"{document_id}: falta campo requerido {key}"
        )
    return value


def _rows_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("documents")
    if not isinstance(rows, list):
        raise SelectiveSemanticCandidateError("Manifest sin documents")
    result: dict[str, dict[str, Any]] = {}
    for value in rows:
        if not isinstance(value, dict):
            continue
        document_id = value.get("canonical_id")
        if not isinstance(document_id, str) or not document_id:
            raise SelectiveSemanticCandidateError(
                "Fila de manifest sin canonical_id válido"
            )
        if document_id in result:
            raise SelectiveSemanticCandidateError(
                f"canonical_id duplicado: {document_id}"
            )
        result[document_id] = dict(value)
    return result


def build_rebased_staged_manifest(
    *,
    current_manifest_path: Path,
    staged_manifest_path: Path,
    current_normalized_root: Path,
    current_metadata_root: Path,
    staged_normalized_root: Path,
    staged_metadata_root: Path,
    output_path: Path,
) -> dict[str, Any]:
    current_payload = _load_json(current_manifest_path)
    staged_payload = _load_json(staged_manifest_path)
    current_rows = _rows_by_id(current_payload)
    staged_rows = _rows_by_id(staged_payload)
    if set(current_rows) != set(staged_rows):
        raise SelectiveSemanticCandidateError(
            "Current y staging no contienen el mismo conjunto documental"
        )

    rebased_rows: list[dict[str, Any]] = []
    for document_id in sorted(staged_rows):
        current = current_rows[document_id]
        staged = dict(staged_rows[document_id])
        normalized_relative = _relative_under(
            _require_string(current, "normalized_path", document_id),
            current_normalized_root,
            f"{document_id}.normalized_path",
        )
        metadata_relative = _relative_under(
            _require_string(current, "metadata_path", document_id),
            current_metadata_root,
            f"{document_id}.metadata_path",
        )
        legal_relative = _relative_under(
            _require_string(current, "legal_metadata_path", document_id),
            current_metadata_root,
            f"{document_id}.legal_metadata_path",
        )
        normalized = staged_normalized_root / normalized_relative
        metadata = staged_metadata_root / metadata_relative
        legal = staged_metadata_root / legal_relative
        for label, path in (
            ("normalized", normalized),
            ("metadata", metadata),
            ("legal_metadata", legal),
        ):
            if not path.is_file():
                raise SelectiveSemanticCandidateError(
                    f"{document_id}: {label} staging ausente: {path}"
                )
        staged["normalized_path"] = str(normalized.resolve())
        staged["metadata_path"] = str(metadata.resolve())
        staged["legal_metadata_path"] = str(legal.resolve())
        rebased_rows.append(staged)

    payload = dict(staged_payload)
    payload["documents"] = rebased_rows
    payload["document_count"] = len(rebased_rows)
    payload["rebased_for_sprint"] = "19I.18J.12.3"
    payload["publication_effect"] = "none"
    _write_json(output_path, payload)
    return payload


def _chunk_document_id(payload: dict[str, Any]) -> str:
    # Canonical chunks used by the existing pipeline keep document identity
    # primarily at top level; retrieval subchunks may keep it under metadata.
    for key in ("document_id", "canonical_id", "source_document_id"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value

    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        for key in ("document_id", "canonical_id", "source_document_id"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value

    raise SelectiveSemanticCandidateError(
        "Chunk sin identidad documental reconocida"
    )


def _document_fingerprints(path: Path) -> dict[str, tuple[int, str]]:
    if not path.is_file():
        raise SelectiveSemanticCandidateError(f"JSONL ausente: {path}")

    grouped: dict[str, list[bytes]] = defaultdict(list)
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise SelectiveSemanticCandidateError(
                        f"{path}:{line_number}: chunk no es objeto"
                    )
                try:
                    document_id = _chunk_document_id(value)
                except SelectiveSemanticCandidateError as exc:
                    raise SelectiveSemanticCandidateError(
                        f"{path}:{line_number}: {exc}"
                    ) from exc
                canonical = json.dumps(
                    value,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                grouped[document_id].append(canonical)
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectiveSemanticCandidateError(
            f"No fue posible leer JSONL: {path}"
        ) from exc

    result: dict[str, tuple[int, str]] = {}
    for document_id, rows in grouped.items():
        rows.sort()
        digest = _sha256_bytes(b"\n".join(rows) + b"\n")
        result[document_id] = (len(rows), digest)
    return result


def audit_semantic_delta(
    current_semantic_path: Path,
    candidate_semantic_path: Path,
) -> tuple[list[SemanticDocumentDelta], list[str]]:
    current = _document_fingerprints(current_semantic_path)
    candidate = _document_fingerprints(candidate_semantic_path)
    if set(current) != set(candidate):
        missing = sorted(set(current) - set(candidate))
        added = sorted(set(candidate) - set(current))
        raise SelectiveSemanticCandidateError(
            f"Conjunto documental semántico cambió; missing={missing}; added={added}"
        )

    deltas = [
        SemanticDocumentDelta(
            document_id=document_id,
            current_count=current[document_id][0],
            candidate_count=candidate[document_id][0],
            current_sha256=current[document_id][1],
            candidate_sha256=candidate[document_id][1],
            changed=current[document_id][1] != candidate[document_id][1],
        )
        for document_id in sorted(current)
    ]
    unauthorized = sorted(
        item.document_id
        for item in deltas
        if item.changed and item.document_id not in AUTHORIZED_DOCUMENTS
    )
    return deltas, unauthorized


def build_selective_semantic_candidate(
    *,
    project_root: Path,
    delta_report_path: Path,
    current_fiscal_manifest_path: Path,
    staged_fiscal_manifest_path: Path,
    current_normalized_root: Path,
    staged_normalized_root: Path,
    current_metadata_root: Path,
    staged_metadata_root: Path,
    prodecon_manifest_path: Path,
    catalog_path: Path,
    raw_baseline_path: Path,
    semantic_baseline_path: Path,
    output_dir: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    delta_report = _load_json(delta_report_path)
    if (
        delta_report.get("sprint") != "19I.18J.12.2"
        or delta_report.get("delta_safe_for_candidate_build") is not True
    ):
        raise SelectiveSemanticCandidateError(
            "J.12.2 aprobado es requisito para construir candidato"
        )
    if set(delta_report.get("source_changed_documents", [])) != AUTHORIZED_DOCUMENTS:
        raise SelectiveSemanticCandidateError(
            "J.12.2 no acredita exactamente los dos reemplazos autorizados"
        )

    resolved_output = output_dir.expanduser().resolve()
    if resolved_output.exists() and not overwrite:
        raise SelectiveSemanticCandidateError(
            f"Salida existente: {resolved_output}; use --overwrite deliberadamente"
        )
    resolved_output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=".j12_3-",
        dir=resolved_output.parent,
    ) as temp_name:
        temp_root = Path(temp_name)
        rebased_manifest = temp_root / "fiscal_manifest_rebased.json"
        raw_candidate = temp_root / "raw_candidate_chunks.jsonl"
        raw_manifest = temp_root / "raw_candidate_manifest.json"
        promoted_candidate = temp_root / "semantic_candidate.jsonl"
        promoted_manifest = temp_root / "semantic_candidate_manifest.json"
        semantic_audit = temp_root / "semantic_candidate_audit.json"

        build_rebased_staged_manifest(
            current_manifest_path=current_fiscal_manifest_path,
            staged_manifest_path=staged_fiscal_manifest_path,
            current_normalized_root=current_normalized_root,
            current_metadata_root=current_metadata_root,
            staged_normalized_root=staged_normalized_root,
            staged_metadata_root=staged_metadata_root,
            output_path=rebased_manifest,
        )

        try:
            build_legal_chunks(
                project_root=root,
                catalog_path=catalog_path,
                fiscal_manifest_path=rebased_manifest,
                prodecon_manifest_path=prodecon_manifest_path,
                chunks_path=raw_candidate,
                manifest_path=raw_manifest,
                overwrite=False,
            )
            promote_semantic_corpus(
                baseline_path=raw_baseline_path,
                candidate_path=raw_candidate,
                normalized_root=staged_normalized_root / "normativa",
                catalog_path=catalog_path,
                promoted_path=promoted_candidate,
                manifest_path=promoted_manifest,
                overwrite=False,
            )
            semantic_report = compare_canonical_corpora(
                baseline_path=semantic_baseline_path,
                candidate_path=promoted_candidate,
            )
            write_semantic_report(semantic_audit, semantic_report)
        except (
            CorpusChunkingError,
            SemanticCanonicalAuditError,
            SemanticCorpusPromotionError,
        ) as exc:
            raise SelectiveSemanticCandidateError(
                f"Pipeline semántico existente rechazó el candidato: {exc}"
            ) from exc

        deltas, unauthorized = audit_semantic_delta(
            semantic_baseline_path,
            promoted_candidate,
        )
        changed = sorted(item.document_id for item in deltas if item.changed)
        ready = not unauthorized and bool(
            AUTHORIZED_DOCUMENTS.intersection(changed)
        )

        report = {
            "sprint": "19I.18J.12.3",
            "mode": "transactional_isolated_semantic_candidate",
            "authorized_documents": sorted(AUTHORIZED_DOCUMENTS),
            "semantic_changed_documents": changed,
            "unauthorized_semantic_changed_documents": unauthorized,
            "candidate_parent_count": sum(
                item.candidate_count for item in deltas
            ),
            "candidate_sha256": _sha256_file(promoted_candidate),
            "candidate_ready_for_transactional_promotion": ready,
            "canonical_mutation_performed": False,
            "runtime_index_mutated": False,
            "public_release_allowed": False,
            "git_push_allowed": False,
            "github_release_allowed": False,
            "render_deploy_allowed": False,
            "documents": [asdict(item) for item in deltas],
        }
        _write_json(temp_root / "selective_semantic_candidate_report.json", report)

        if resolved_output.exists():
            shutil.rmtree(resolved_output)
        os.replace(temp_root, resolved_output)

    return _load_json(
        resolved_output / "selective_semantic_candidate_report.json"
    )
