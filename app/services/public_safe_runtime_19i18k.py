from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

EXPECTED_NORMATIVE_DOCUMENTS = {
    "cff", "cpeum", "lfdc", "lfisan", "lfpca", "lieps", "lif_2026",
    "lisr", "liva", "lotfja", "reg_cff", "reg_lisr_060516",
    "reg_liva_250914", "rmf_2026",
}
BLOCKED_PUBLIC_DOCUMENTS = {
    "manual_unam", "manual_derecho_fiscal_unam", "prodecon",
    "prodecon_contribuyente",
}
EXPECTED_CANONICAL_SHA256 = (
    "4d040043173c625ca09ed2ae954aa2bdf01993989f1a52997d7acbb067fee25c"
)
EXPECTED_CANONICAL_PARENTS = 2981

REFERENCE_THRESHOLDS = {
    "Hit@1(any)": 1.0, "Hit@3(any)": 1.0, "Hit@K(any)": 1.0,
    "MRR(any)": 1.0, "PrimaryHit@1": 0.917, "PrimaryHit@3": 0.917,
    "PrimaryHit@K": 1.0, "PrimaryMRR": 0.938,
}


class PublicSafeRuntimeError(RuntimeError):
    """Fail-closed error for Sprint 19I.18K."""


@dataclass(frozen=True)
class CommandResult:
    command: list[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class FilterResult:
    parent_count: int
    document_ids: list[str]
    blocked_removed: list[str]
    sha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicSafeRuntimeError(f"JSON inválido: {path}") from exc


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _document_id(row: dict[str, Any]) -> str:
    for key in ("document_id", "canonical_id", "source_document_id"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    metadata = row.get("metadata")
    if isinstance(metadata, dict):
        for key in ("document_id", "canonical_id", "source_document_id"):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                return value
    raise PublicSafeRuntimeError("Chunk sin identidad documental explícita")


def _normalize_public_id(document_id: str) -> str:
    aliases = {
        "manual_derecho_fiscal_unam": "manual_unam",
        "prodecon_contribuyente": "prodecon",
    }
    return aliases.get(document_id, document_id)


def build_normative_only_canonical(
    input_path: Path,
    output_path: Path,
) -> FilterResult:
    if not input_path.is_file():
        raise PublicSafeRuntimeError(f"Canonical ausente: {input_path}")
    kept: list[str] = []
    observed: set[str] = set()
    removed: set[str] = set()
    unknown: set[str] = set()
    with input_path.open("r", encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PublicSafeRuntimeError(
                    f"{input_path}:{line_number}: JSON inválido"
                ) from exc
            if not isinstance(row, dict):
                raise PublicSafeRuntimeError(
                    f"{input_path}:{line_number}: objeto esperado"
                )
            document_id = _normalize_public_id(_document_id(row))
            observed.add(document_id)
            if document_id in {"manual_unam", "prodecon"}:
                removed.add(document_id)
                continue
            if document_id not in EXPECTED_NORMATIVE_DOCUMENTS:
                unknown.add(document_id)
                continue
            kept.append(line if line.endswith("\n") else line + "\n")
    if unknown:
        raise PublicSafeRuntimeError(
            f"Documentos desconocidos en canonical: {sorted(unknown)}"
        )
    kept_documents = observed - {"manual_unam", "prodecon"}
    if kept_documents != EXPECTED_NORMATIVE_DOCUMENTS:
        raise PublicSafeRuntimeError(
            "Composición normativa inválida; "
            f"missing={sorted(EXPECTED_NORMATIVE_DOCUMENTS-kept_documents)}; "
            f"extra={sorted(kept_documents-EXPECTED_NORMATIVE_DOCUMENTS)}"
        )
    if removed != {"manual_unam", "prodecon"}:
        raise PublicSafeRuntimeError(
            "El canonical no contiene exactamente las dos capas públicas bloqueadas"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(kept), encoding="utf-8")
    return FilterResult(
        len(kept), sorted(kept_documents), sorted(removed), _sha256(output_path)
    )


def _prune_manifest_value(value: Any) -> Any:
    if isinstance(value, list):
        result = []
        for item in value:
            if isinstance(item, dict):
                try:
                    document_id = _normalize_public_id(_document_id(item))
                except PublicSafeRuntimeError:
                    document_id = ""
                if document_id in {"manual_unam", "prodecon"}:
                    continue
            if isinstance(item, str) and _normalize_public_id(item) in {
                "manual_unam", "prodecon"
            }:
                continue
            result.append(_prune_manifest_value(item))
        return result
    if isinstance(value, dict):
        return {key: _prune_manifest_value(item) for key, item in value.items()}
    return value


def build_public_manifest(
    input_manifest_path: Path,
    output_manifest_path: Path,
    *,
    old_canonical_path: Path,
    new_canonical_path: Path,
    old_parent_count: int,
    new_parent_count: int,
    old_sha256: str,
    new_sha256: str,
) -> None:
    payload = _prune_manifest_value(_load_json(input_manifest_path))

    # J.18K-r3: the 19I.8 rebuild validates the exact manifest field
    # `promoted_chunks`. The previous generic regex did not match that key.
    exact_count_keys = {
        "promoted_chunks",
        "parent_count",
        "parent_chunks",
        "promoted_count",
        "chunk_count",
        "chunks_count",
        "total_chunks",
        "total_parents",
    }
    count_key = re.compile(
        r"(parent|chunk|promoted).*(count|total)|(count|total).*(parent|chunk)"
    )
    hash_key = re.compile(r"(sha256|hash)")
    path_key = re.compile(
        r"(canonical|chunk).*(path|file)|(path|file).*(canonical|chunk)"
    )

    def rewrite(value: Any, key: str = "") -> Any:
        lowered = key.casefold()
        if isinstance(value, dict):
            return {k: rewrite(v, k) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(item, key) for item in value]
        if (
            isinstance(value, int)
            and value == old_parent_count
            and (lowered in exact_count_keys or count_key.search(lowered))
        ):
            return new_parent_count
        if isinstance(value, str):
            if value == old_sha256 and hash_key.search(lowered):
                return new_sha256
            if path_key.search(lowered):
                try:
                    if Path(value).name == old_canonical_path.name:
                        return str(new_canonical_path.resolve())
                except (OSError, ValueError):
                    pass
        return value

    rewritten = rewrite(payload)
    if not isinstance(rewritten, dict):
        raise PublicSafeRuntimeError("Manifest canonical debe ser un objeto JSON")

    # Fail closed on the exact invariant consumed by rebuild_semantic_runtime_19i8.
    if "promoted_chunks" in rewritten:
        rewritten["promoted_chunks"] = new_parent_count
    rewritten["public_runtime_scope"] = "normative_only"
    rewritten["public_runtime_document_count"] = len(EXPECTED_NORMATIVE_DOCUMENTS)
    rewritten["public_runtime_parent_count"] = new_parent_count
    rewritten["public_runtime_canonical_sha256"] = new_sha256
    rewritten["excluded_public_documents"] = ["manual_unam", "prodecon"]
    rewritten["sprint"] = "19I.18K"
    _write_json(output_manifest_path, rewritten)


def _run(command: list[str]) -> CommandResult:
    completed = subprocess.run(
        command, check=False, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    result = CommandResult(
        command, completed.returncode, completed.stdout, completed.stderr
    )
    if result.returncode != 0:
        raise PublicSafeRuntimeError(
            "Comando controlado falló:\n" + " ".join(command)
            + "\nSTDOUT:\n" + result.stdout + "\nSTDERR:\n" + result.stderr
        )
    return result


def parse_metrics(output: str) -> dict[str, float]:
    keys = [
        "Hit@1(any)", "Hit@3(any)", "Hit@K(any)", "MRR(any)",
        "PrimaryHit@1", "PrimaryHit@3", "PrimaryHit@K", "PrimaryMRR",
        "MeanUniqueDocs@K",
    ]
    metrics: dict[str, float] = {}
    for key in keys:
        match = re.search(
            rf"(?m)^{re.escape(key)}=([0-9]+(?:\.[0-9]+)?)\s*$", output
        )
        if match is None:
            raise PublicSafeRuntimeError(f"Métrica ausente: {key}")
        metrics[key] = float(match.group(1))
    return metrics


def _collect_expected_document_ids(value: Any) -> set[str]:
    found: set[str] = set()
    def walk(node: Any, key: str = "") -> None:
        lowered = key.casefold()
        if isinstance(node, dict):
            for child_key, child in node.items():
                walk(child, child_key)
        elif isinstance(node, list):
            for child in node:
                walk(child, key)
        elif isinstance(node, str) and (
            "document" in lowered or lowered in {"doc_id", "primary_doc", "source_id"}
        ):
            normalized = _normalize_public_id(node)
            if normalized in EXPECTED_NORMATIVE_DOCUMENTS | {"manual_unam", "prodecon"}:
                found.add(normalized)
    walk(value)
    return found


def build_normative_eval_cases(input_path: Path, output_path: Path) -> int:
    payload = _load_json(input_path)
    if isinstance(payload, dict):
        cases = payload.get("cases")
        if not isinstance(cases, list):
            raise PublicSafeRuntimeError("Dataset de evaluación sin lista 'cases'")
        wrapper = dict(payload)
    elif isinstance(payload, list):
        cases = payload
        wrapper = None
    else:
        raise PublicSafeRuntimeError("Formato de casos de evaluación no soportado")
    selected: list[Any] = []
    for case in cases:
        if not isinstance(case, dict):
            continue
        refs = _collect_expected_document_ids(case)
        if refs and refs <= EXPECTED_NORMATIVE_DOCUMENTS:
            selected.append(case)
    if not selected:
        raise PublicSafeRuntimeError(
            "No se pudieron derivar casos normativos del benchmark existente"
        )
    if wrapper is None:
        output_payload: Any = selected
    else:
        wrapper["cases"] = selected
        wrapper["sprint_filter"] = "19I.18K normative-only"
        output_payload = wrapper
    _write_json(output_path, output_payload)
    return len(selected)


def assert_blocked_content_absent(paths: Iterable[Path]) -> None:
    blocked_ids = (
        "manual_unam", "manual_derecho_fiscal_unam",
        "prodecon", "prodecon_contribuyente",
    )
    patterns = tuple(
        pattern
        for document_id in blocked_ids
        for pattern in (
            f'"document_id":"{document_id}"',
            f'"document_id": "{document_id}"',
            f'"canonical_id":"{document_id}"',
            f'"canonical_id": "{document_id}"',
        )
    )
    violations: list[str] = []
    for root in paths:
        if not root.exists():
            raise PublicSafeRuntimeError(f"Artefacto runtime ausente: {root}")
        candidates = [root] if root.is_file() else root.rglob("*")
        for path in candidates:
            if not path.is_file() or path.suffix.casefold() not in {
                ".json", ".jsonl", ".txt"
            }:
                continue
            text = path.read_text(encoding="utf-8", errors="replace").casefold()
            if any(pattern in text for pattern in patterns):
                violations.append(str(path))
    if violations:
        raise PublicSafeRuntimeError(
            f"Contenido bloqueado detectado en runtime público: {violations}"
        )


def execute_public_safe_runtime(
    *,
    canonical_path: Path,
    canonical_manifest_path: Path,
    output_dir: Path,
    cases_path: Path,
    policy_path: Path,
    batch_size: int = 32,
    local_files_only: bool = True,
) -> dict[str, Any]:
    if _sha256(canonical_path) != EXPECTED_CANONICAL_SHA256:
        raise PublicSafeRuntimeError(
            "Canonical actual no coincide con el SHA aprobado por J.12.4"
        )
    if output_dir.exists():
        raise PublicSafeRuntimeError(
            f"Output ya existe: {output_dir}; revisar antes de reintentar"
        )
    output_dir.mkdir(parents=True)

    public_canonical = output_dir / "canonical" / "chunks_semantic_v2_normative.jsonl"
    public_manifest = output_dir / "canonical" / "manifest_normative.json"
    public_cases = output_dir / "evaluation" / "retrieval_eval_cases_normative.json"
    retrieval_dir = output_dir / "retrieval"
    runtime_dir = output_dir / "runtime"

    filtered = build_normative_only_canonical(canonical_path, public_canonical)
    build_public_manifest(
        canonical_manifest_path, public_manifest,
        old_canonical_path=canonical_path,
        new_canonical_path=public_canonical,
        old_parent_count=EXPECTED_CANONICAL_PARENTS,
        new_parent_count=filtered.parent_count,
        old_sha256=EXPECTED_CANONICAL_SHA256,
        new_sha256=filtered.sha256,
    )
    normative_case_count = build_normative_eval_cases(cases_path, public_cases)

    rebuild_command = [
        sys.executable, "-m", "scripts.rebuild_semantic_runtime_19i8",
        "--canonical", str(public_canonical),
        "--manifest", str(public_manifest),
        "--retrieval-dir", str(retrieval_dir),
        "--runtime-dir", str(runtime_dir),
        "--expected-parents", str(filtered.parent_count),
        "--batch-size", str(batch_size), "--stage", "all",
    ]
    if local_files_only:
        rebuild_command.append("--local-files-only")
    rebuild = _run(rebuild_command)

    benchmark_command = [
        sys.executable, "-m", "scripts.evaluate_runtime_retrieval_19g",
        "--index-dir", str(runtime_dir), "--cases", str(public_cases),
        "--policy", str(policy_path),
    ]
    if local_files_only:
        benchmark_command.append("--local-files-only")
    benchmark = _run(benchmark_command)
    metrics = parse_metrics(benchmark.stdout)
    benchmark_passed = all(
        metrics[key] >= threshold for key, threshold in REFERENCE_THRESHOLDS.items()
    )
    assert_blocked_content_absent([public_canonical, retrieval_dir, runtime_dir])

    report = {
        "sprint": "19I.18K",
        "status": "public_safe_runtime_local_acceptance",
        "scope": "normative_only",
        "normative_documents": filtered.document_ids,
        "normative_document_count": len(filtered.document_ids),
        "excluded_documents": filtered.blocked_removed,
        "parent_count": filtered.parent_count,
        "canonical_sha256": filtered.sha256,
        "normative_eval_case_count": normative_case_count,
        "metrics": metrics,
        "benchmark_thresholds": REFERENCE_THRESHOLDS,
        "benchmark_passed": benchmark_passed,
        "blocked_content_absent": True,
        "technical_local_acceptance": benchmark_passed,
        "legal_basis_status": "statutory_text_exclusion_candidate_with_human_review_required",
        "redistribution_human_review_required": True,
        "temporal_validity_gate_required": True,
        "temporal_validity_complete": False,
        "manual_unam_publicly_excluded": True,
        "prodecon_publicly_excluded": True,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "automatic_legal_promotion_performed": False,
        "rebuild": asdict(rebuild),
        "benchmark": asdict(benchmark),
    }
    _write_json(output_dir / "public_safe_runtime_acceptance.json", report)
    if not benchmark_passed:
        raise PublicSafeRuntimeError(
            "Runtime normativo construido, pero benchmark quedó bajo umbral"
        )
    return report
