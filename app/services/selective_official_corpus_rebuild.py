from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

TARGETS = ("lfdc", "reg_liva_250914")
MAX_PDF_BYTES = 50 * 1024 * 1024


class SelectiveOfficialRebuildError(RuntimeError):
    """Controlled error for the selective official-source rebuild."""


@dataclass(frozen=True)
class TargetSource:
    document_id: str
    local_pdf: Path
    official_pdf: Path
    local_sha256: str
    official_sha256: str


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SelectiveOfficialRebuildError(f"JSON inválido: {path}") from exc
    if not isinstance(value, dict):
        raise SelectiveOfficialRebuildError(f"Objeto JSON esperado: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _validate_pdf(path: Path, expected_sha: str) -> None:
    if not path.is_file():
        raise SelectiveOfficialRebuildError(f"PDF ausente: {path}")
    size = path.stat().st_size
    if size <= 0 or size > MAX_PDF_BYTES:
        raise SelectiveOfficialRebuildError(f"Tamaño PDF inválido: {path}")
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise SelectiveOfficialRebuildError(f"Firma PDF inválida: {path}")
    actual = _sha256(path)
    if actual.casefold() != expected_sha.casefold():
        raise SelectiveOfficialRebuildError(
            f"SHA-256 no coincide para {path}: {actual}"
        )


def _required_string(
    row: dict[str, Any],
    key: str,
    document_id: str,
) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise SelectiveOfficialRebuildError(
            f"{document_id}: campo requerido inválido: {key}"
        )
    return value


def _targets(plan: dict[str, Any]) -> list[TargetSource]:
    if plan.get("sprint") != "19I.18J.12":
        raise SelectiveOfficialRebuildError("Plan J.12 requerido")
    if plan.get("rebuild_authorized") is not True:
        raise SelectiveOfficialRebuildError("J.12 no autoriza reconstrucción")
    rows = plan.get("targets")
    if not isinstance(rows, list):
        raise SelectiveOfficialRebuildError("Targets J.12 inválidos")

    result: list[TargetSource] = []
    for item in rows:
        if not isinstance(item, dict):
            continue
        row = cast(dict[str, Any], item)
        document_id = row.get("document_id")
        if not isinstance(document_id, str) or document_id not in TARGETS:
            raise SelectiveOfficialRebuildError(
                f"Target no permitido: {document_id}"
            )

        local_pdf = _required_string(row, "local_pdf", document_id)
        official_pdf = _required_string(row, "official_pdf", document_id)
        local_sha256 = _required_string(row, "local_sha256", document_id)
        official_sha256 = _required_string(row, "official_sha256", document_id)

        result.append(
            TargetSource(
                document_id=document_id,
                local_pdf=Path(local_pdf),
                official_pdf=Path(official_pdf),
                local_sha256=local_sha256,
                official_sha256=official_sha256,
            )
        )

    if {item.document_id for item in result} != set(TARGETS):
        raise SelectiveOfficialRebuildError(
            "J.12 debe contener exactamente LFDC y Reglamento LIVA"
        )
    return result


def _copy_corpus(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise SelectiveOfficialRebuildError(f"Corpus local inválido: {source}")
    destination.mkdir(parents=True, exist_ok=False)
    pdfs = list(source.glob("*.pdf"))
    if not pdfs:
        raise SelectiveOfficialRebuildError("El corpus local no contiene PDF")
    for pdf in pdfs:
        shutil.copy2(pdf, destination / pdf.name)


def _replace_by_local_identity(
    staging_corpus: Path,
    target: TargetSource,
) -> tuple[str, str]:
    matches = [
        item
        for item in staging_corpus.glob("*.pdf")
        if _sha256(item).casefold() == target.local_sha256.casefold()
    ]
    if len(matches) != 1:
        raise SelectiveOfficialRebuildError(
            f"{target.document_id}: se esperaba un PDF local por SHA; "
            f"encontrados={len(matches)}"
        )
    destination = matches[0]
    before_name = destination.name
    shutil.copy2(target.official_pdf, destination)
    if _sha256(destination).casefold() != target.official_sha256.casefold():
        raise SelectiveOfficialRebuildError(
            f"{target.document_id}: sustitución de staging no verificable"
        )
    return before_name, target.official_sha256


def _run(command: list[str], cwd: Path) -> None:
    completed = subprocess.run(command, cwd=cwd, check=False)
    if completed.returncode != 0:
        raise SelectiveOfficialRebuildError(
            "Falló pipeline existente: " + " ".join(command)
        )


def stage_official_rebuild(
    *,
    project_root: Path,
    local_corpus_dir: Path,
    plan_path: Path,
    output_dir: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    root = project_root.expanduser().resolve()
    plan = _load_json(plan_path)
    targets = _targets(plan)

    for target in targets:
        _validate_pdf(target.local_pdf, target.local_sha256)
        _validate_pdf(target.official_pdf, target.official_sha256)

    resolved_output = output_dir.expanduser().resolve()
    if resolved_output.exists() and not overwrite:
        raise SelectiveOfficialRebuildError(
            f"Salida existente: {resolved_output}; use --overwrite"
        )
    resolved_output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=".j12_1-",
        dir=resolved_output.parent,
    ) as temp_name:
        temp_root = Path(temp_name)
        staging_corpus = temp_root / "corpus"
        staged_knowledge = temp_root / "knowledge"
        _copy_corpus(local_corpus_dir.expanduser().resolve(), staging_corpus)

        replacements: dict[str, dict[str, str]] = {}
        for target in targets:
            filename, sha = _replace_by_local_identity(staging_corpus, target)
            replacements[target.document_id] = {
                "staged_filename": filename,
                "official_sha256": sha,
            }

        normalized = staged_knowledge / "normalized"
        metadata = staged_knowledge / "metadata"
        legal_metadata = metadata / "legal"
        manifest = metadata / "fiscal_corpus_15_manifest.json"

        command = [
            sys.executable,
            "-m",
            "scripts.integrate_fiscal_corpus",
            "--corpus-dir",
            str(staging_corpus),
            "--catalog",
            str(root / "app/resources/fiscal_corpus_15_catalog.json"),
            "--normalized-root",
            str(normalized),
            "--metadata-dir",
            str(metadata),
            "--legal-metadata-dir",
            str(legal_metadata),
            "--manifest",
            str(manifest),
            "--overwrite",
        ]
        _run(command, root)

        if not manifest.is_file():
            raise SelectiveOfficialRebuildError(
                "El pipeline no produjo fiscal_corpus_15_manifest.json"
            )
        staged_manifest = _load_json(manifest)

        audit = {
            "sprint": "19I.18J.12.1",
            "mode": "isolated_staging_rebuild",
            "target_documents": list(TARGETS),
            "replacements": replacements,
            "source_plan": str(plan_path),
            "local_corpus_mutated": False,
            "canonical_semantic_mutated": False,
            "runtime_index_mutated": False,
            "staged_integration_completed": True,
            "public_release_allowed": False,
            "git_push_allowed": False,
            "github_release_allowed": False,
            "render_deploy_allowed": False,
        }
        (temp_root / "rebuild_audit.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        if resolved_output.exists():
            shutil.rmtree(resolved_output)
        os.replace(temp_root, resolved_output)

    report = _load_json(resolved_output / "rebuild_audit.json")
    report["staged_manifest_document_count"] = staged_manifest.get(
        "document_count"
    )
    (resolved_output / "rebuild_audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report
