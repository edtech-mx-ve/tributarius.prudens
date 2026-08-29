from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

EXPECTED_CANDIDATE_SHA256 = (
    "4d040043173c625ca09ed2ae954aa2bdf01993989f1a52997d7acbb067fee25c"
)
EXPECTED_PARENT_COUNT = 2981

_THRESHOLDS = {
    "Hit@1(any)": 1.0,
    "Hit@3(any)": 1.0,
    "Hit@K(any)": 1.0,
    "MRR(any)": 1.0,
    "PrimaryHit@1": 0.917,
    "PrimaryHit@3": 0.917,
    "PrimaryHit@K": 1.0,
    "PrimaryMRR": 0.938,
    "MeanUniqueDocs@K": 2.333,
}


class TransactionalRagPromotionError(RuntimeError):
    """Fail-closed error for Sprint 19I.18J.12.4."""


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TransactionalRagPromotionError(f"JSON inválido: {path}") from exc
    if not isinstance(value, dict):
        raise TransactionalRagPromotionError(f"Objeto JSON esperado: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _run(command: list[str]) -> CommandResult:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    result = CommandResult(
        command=command,
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
    if result.returncode != 0:
        raise TransactionalRagPromotionError(
            "Comando controlado falló:\n"
            + " ".join(command)
            + "\nSTDOUT:\n"
            + result.stdout
            + "\nSTDERR:\n"
            + result.stderr
        )
    return result


def parse_retrieval_metrics(output: str) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for key in _THRESHOLDS:
        match = re.search(
            rf"(?m)^{re.escape(key)}=([0-9]+(?:\.[0-9]+)?)\s*$",
            output,
        )
        if match is None:
            raise TransactionalRagPromotionError(
                f"Métrica ausente en benchmark: {key}"
            )
        metrics[key] = float(match.group(1))
    return metrics


def benchmark_passes(metrics: dict[str, float]) -> bool:
    return all(metrics[key] >= threshold for key, threshold in _THRESHOLDS.items())


def _validate_candidate(
    candidate_dir: Path,
    expected_sha256: str,
) -> tuple[Path, Path, dict[str, Any]]:
    report_path = candidate_dir / "selective_semantic_candidate_report.json"
    candidate_path = candidate_dir / "semantic_candidate.jsonl"
    manifest_path = candidate_dir / "semantic_candidate_manifest.json"
    report = _load_json(report_path)

    if report.get("sprint") != "19I.18J.12.3":
        raise TransactionalRagPromotionError("Candidato no pertenece a J.12.3")
    if report.get("candidate_ready_for_transactional_promotion") is not True:
        raise TransactionalRagPromotionError("Candidato J.12.3 no aprobado")
    if report.get("candidate_parent_count") != EXPECTED_PARENT_COUNT:
        raise TransactionalRagPromotionError("Cardinalidad de parents inesperada")
    if report.get("unauthorized_semantic_changed_documents") != []:
        raise TransactionalRagPromotionError("Candidato contiene cambios no autorizados")
    if set(report.get("semantic_changed_documents", [])) != {
        "lfdc",
        "reg_liva_250914",
    }:
        raise TransactionalRagPromotionError(
            "Delta semántico no coincide con documentos autorizados"
        )
    for path in (candidate_path, manifest_path):
        if not path.is_file():
            raise TransactionalRagPromotionError(f"Artefacto candidato ausente: {path}")

    actual_sha = _sha256(candidate_path)
    if actual_sha != expected_sha256 or report.get("candidate_sha256") != actual_sha:
        raise TransactionalRagPromotionError(
            f"SHA candidato no coincide; esperado={expected_sha256}; actual={actual_sha}"
        )
    return candidate_path, manifest_path, report


def _safe_remove(path: Path) -> None:
    if not path.exists():
        return
    if path.is_dir():
        shutil.rmtree(path)
    else:
        path.unlink()


def _copy_artifact(source: Path, target: Path) -> None:
    if source.is_dir():
        shutil.copytree(source, target)
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _transactional_promote(
    replacements: list[tuple[Path, Path]],
    snapshot_dir: Path,
) -> None:
    snapshot_dir.mkdir(parents=True, exist_ok=False)
    staged: list[tuple[Path, Path]] = []
    backups: list[tuple[Path, Path]] = []

    try:
        for index, (source, target) in enumerate(replacements):
            if not source.exists():
                raise TransactionalRagPromotionError(
                    f"Fuente de promoción ausente: {source}"
                )
            target.parent.mkdir(parents=True, exist_ok=True)
            incoming = target.parent / f".{target.name}.j12_4_incoming_{index}"
            _safe_remove(incoming)
            _copy_artifact(source, incoming)
            staged.append((incoming, target))

        for _, target in staged:
            if target.exists():
                backup = snapshot_dir / f"{len(backups):02d}_{target.name}"
                _copy_artifact(target, backup)
                backups.append((backup, target))

        for incoming, target in staged:
            if target.exists():
                _safe_remove(target)
            os.replace(incoming, target)

    except Exception as exc:
        backup_targets = {target for _, target in backups}
        for _, target in replacements:
            if target.exists():
                _safe_remove(target)
            if target not in backup_targets:
                continue
            backup = next(
                backup_path
                for backup_path, backup_target in backups
                if backup_target == target
            )
            _copy_artifact(backup, target)
        for incoming, _ in staged:
            _safe_remove(incoming)
        raise TransactionalRagPromotionError(
            f"Promoción falló y se ejecutó rollback: {exc}"
        ) from exc


def execute_transactional_rag_promotion(
    *,
    project_root: Path,
    candidate_dir: Path,
    work_dir: Path,
    snapshot_root: Path,
    canonical_path: Path,
    canonical_manifest_path: Path,
    retrieval_target: Path,
    runtime_target: Path,
    cases_path: Path,
    policy_path: Path,
    expected_sha256: str = EXPECTED_CANDIDATE_SHA256,
    local_files_only: bool = True,
    batch_size: int = 32,
) -> dict[str, Any]:
    # Resolve deliberately to validate the caller-provided project root even
    # though the existing rebuild/evaluation CLIs consume explicit paths.
    project_root.resolve()
    candidate_path, candidate_manifest, candidate_report = _validate_candidate(
        candidate_dir.resolve(),
        expected_sha256,
    )

    resolved_work = work_dir.resolve()
    if resolved_work.exists():
        raise TransactionalRagPromotionError(
            f"Work dir ya existe: {resolved_work}; revisar antes de reintentar"
        )
    resolved_work.mkdir(parents=True)

    staged_retrieval = resolved_work / "retrieval"
    staged_runtime = resolved_work / "runtime"

    rebuild_command = [
        sys.executable,
        "-m",
        "scripts.rebuild_semantic_runtime_19i8",
        "--canonical",
        str(candidate_path),
        "--manifest",
        str(candidate_manifest),
        "--retrieval-dir",
        str(staged_retrieval),
        "--runtime-dir",
        str(staged_runtime),
        "--expected-parents",
        str(EXPECTED_PARENT_COUNT),
        "--batch-size",
        str(batch_size),
        "--stage",
        "all",
    ]
    if local_files_only:
        rebuild_command.append("--local-files-only")
    rebuild = _run(rebuild_command)

    benchmark_command = [
        sys.executable,
        "-m",
        "scripts.evaluate_runtime_retrieval_19g",
        "--index-dir",
        str(staged_runtime),
        "--cases",
        str(cases_path),
        "--policy",
        str(policy_path),
    ]
    if local_files_only:
        benchmark_command.append("--local-files-only")
    benchmark = _run(benchmark_command)
    metrics = parse_retrieval_metrics(benchmark.stdout)

    pre_promotion_report = {
        "sprint": "19I.18J.12.4",
        "phase": "pre_promotion_benchmark",
        "candidate_sha256": expected_sha256,
        "candidate_parent_count": EXPECTED_PARENT_COUNT,
        "metrics": metrics,
        "thresholds": _THRESHOLDS,
        "benchmark_passed": benchmark_passes(metrics),
        "canonical_mutation_performed": False,
        "runtime_mutation_performed": False,
        "public_release_allowed": False,
        "rebuild": asdict(rebuild),
        "benchmark": asdict(benchmark),
    }
    _write_json(resolved_work / "pre_promotion_report.json", pre_promotion_report)

    if not pre_promotion_report["benchmark_passed"]:
        raise TransactionalRagPromotionError(
            "Benchmark de regresión no alcanzó los umbrales; no se promovió nada"
        )

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    snapshot_dir = snapshot_root.resolve() / f"j12_4_{stamp}"
    replacements = [
        (candidate_path, canonical_path.resolve()),
        (candidate_manifest, canonical_manifest_path.resolve()),
        (staged_retrieval, retrieval_target.resolve()),
        (staged_runtime, runtime_target.resolve()),
    ]
    _transactional_promote(replacements, snapshot_dir)

    canonical_sha = _sha256(canonical_path.resolve())
    if canonical_sha != expected_sha256:
        raise TransactionalRagPromotionError(
            "Verificación post-promoción falló: SHA canonical inesperado"
        )

    report = {
        "sprint": "19I.18J.12.4",
        "status": "transactional_promotion_completed",
        "candidate_sha256": expected_sha256,
        "canonical_sha256": canonical_sha,
        "parent_count": EXPECTED_PARENT_COUNT,
        "semantic_changed_documents": candidate_report[
            "semantic_changed_documents"
        ],
        "metrics": metrics,
        "thresholds": _THRESHOLDS,
        "benchmark_passed": True,
        "snapshot_dir": str(snapshot_dir),
        "canonical_mutation_performed": True,
        "runtime_mutation_performed": True,
        "rollback_snapshot_created": True,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
    }
    _write_json(resolved_work / "transactional_promotion_report.json", report)
    return report
