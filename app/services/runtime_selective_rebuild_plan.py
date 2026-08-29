from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

ALLOWED_TARGETS = ("lfdc", "reg_liva_250914")


class SelectiveRebuildPlanError(RuntimeError):
    """Raised when a safe selective rebuild plan cannot be produced."""


@dataclass(frozen=True)
class RebuildTarget:
    document_id: str
    classification: str
    text_similarity: float
    official_pdf: str
    official_sha256: str
    local_pdf: str
    local_sha256: str
    actions: tuple[str, ...]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectiveRebuildPlanError(f"JSON inválido o ausente: {path}") from exc
    if not isinstance(value, dict):
        raise SelectiveRebuildPlanError(f"Se esperaba objeto JSON: {path}")
    return value


def _document_rows(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    raw = payload.get("documents")
    if not isinstance(raw, list):
        raise SelectiveRebuildPlanError("J.11 no contiene lista 'documents'")
    rows: dict[str, dict[str, Any]] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        document_id = item.get("document_id")
        if isinstance(document_id, str):
            rows[document_id] = item
    return rows


def _required_str(row: dict[str, Any], key: str, document_id: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise SelectiveRebuildPlanError(
            f"{document_id}: campo requerido ausente: {key}"
        )
    return value


def _profile_sha(row: dict[str, Any], key: str, document_id: str) -> str:
    profile = row.get(key)
    if not isinstance(profile, dict):
        raise SelectiveRebuildPlanError(
            f"{document_id}: perfil requerido ausente: {key}"
        )
    sha = profile.get("sha256")
    if not isinstance(sha, str) or len(sha) != 64:
        raise SelectiveRebuildPlanError(
            f"{document_id}: SHA-256 inválido en {key}"
        )
    return sha.casefold()


def build_selective_rebuild_plan(
    *,
    differential_report_path: Path,
    output_path: Path,
) -> dict[str, Any]:
    differential = _load_json(differential_report_path)
    if differential.get("sprint") != "19I.18J.11":
        raise SelectiveRebuildPlanError("El reporte no pertenece a J.11")

    material = differential.get("material_textual_difference_documents")
    if not isinstance(material, list):
        raise SelectiveRebuildPlanError(
            "J.11 no contiene material_textual_difference_documents"
        )

    material_ids = tuple(item for item in material if isinstance(item, str))
    unexpected = sorted(set(material_ids) - set(ALLOWED_TARGETS))
    if unexpected:
        raise SelectiveRebuildPlanError(
            f"Targets no autorizados para reconstrucción: {','.join(unexpected)}"
        )
    if not material_ids:
        raise SelectiveRebuildPlanError(
            "No existen diferencias textuales materiales que reconstruir"
        )

    rows = _document_rows(differential)
    targets: list[RebuildTarget] = []
    for document_id in material_ids:
        row = rows.get(document_id)
        if row is None:
            raise SelectiveRebuildPlanError(
                f"Falta detalle J.11 para {document_id}"
            )
        classification = _required_str(row, "classification", document_id)
        if classification != "material_textual_difference_detected":
            raise SelectiveRebuildPlanError(
                f"{document_id}: clasificación incompatible: {classification}"
            )

        similarity = row.get("text_similarity")
        if not isinstance(similarity, (int, float)):
            raise SelectiveRebuildPlanError(
                f"{document_id}: text_similarity inválido"
            )

        targets.append(
            RebuildTarget(
                document_id=document_id,
                classification=classification,
                text_similarity=float(similarity),
                official_pdf=_required_str(row, "official_pdf", document_id),
                official_sha256=_profile_sha(row, "official", document_id),
                local_pdf=_required_str(row, "local_pdf", document_id),
                local_sha256=_profile_sha(row, "local", document_id),
                actions=(
                    "snapshot_current_document_artifacts",
                    "use_verified_official_pdf_as_new_source",
                    "reextract_normalized_markdown",
                    "redetect_legal_structure",
                    "rebuild_parent_chunks_for_document_only",
                    "rebuild_subchunks_for_document_only",
                    "rebuild_runtime_vector_index_atomically",
                    "rerun_retrieval_and_rag_regression",
                    "rerun_temporal_and_publication_gates",
                ),
            )
        )

    report = {
        "sprint": "19I.18J.12",
        "mode": "plan_only_fail_closed",
        "targets": [asdict(target) for target in targets],
        "target_documents": [target.document_id for target in targets],
        "target_count": len(targets),
        "untouched_documents_policy": (
            "all_documents_except_targets_must_remain_byte_and_record_identical"
        ),
        "requires_backup_before_mutation": True,
        "requires_atomic_index_replacement": True,
        "requires_post_rebuild_regression": True,
        "rebuild_authorized": True,
        "rebuild_executed": False,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
