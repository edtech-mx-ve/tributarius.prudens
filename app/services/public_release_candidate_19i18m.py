from __future__ import annotations

import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

from app.services.runtime_inner_integrity_19s_r10 import (
    RuntimeInnerIntegrityError,
    validate_runtime_inner_integrity,
)

PUBLIC_CANONICAL_SHA256 = (
    "7b4bb564cdfbd849a961790bcfad938d09369ffc41edc2de4cedce1cab2c49b0"
)
PUBLIC_PARENT_COUNT = 2962
FIXED_ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)
MAX_TOTAL_BYTES = 500 * 1024 * 1024

BLOCKED_DOCUMENT_IDS = {
    "manual_unam",
    "manual_derecho_fiscal_unam",
    "prodecon",
    "prodecon_contribuyente",
}
IDENTITY_KEYS = {"document_id", "canonical_id", "source_document_id"}
FORBIDDEN_SUFFIXES = {
    ".pdf",
    ".md",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".safetensors",
    ".pt",
    ".pth",
    ".onnx",
}
SECRET_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|secret|password|access[_-]?token|bearer)\b"
    r"\s*[:=]\s*[\"']?[A-Za-z0-9_\-./+=]{12,}"
)
WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?i)(?<![A-Za-z0-9_])"
    r"[A-Z]:\\"
    r"(?:[^\\/:*?\"<>|\r\n]+\\)*"
    r"[^\\/:*?\"<>|\r\n]+"
)
POSIX_PRIVATE_PATH = re.compile(
    r"(?<![A-Za-z0-9_])/(?:Users|home)/[^/\s]+/(?:[^/\r\n]+/)*[^/\r\n]+"
)
FULL_WINDOWS_ABSOLUTE_PATH = re.compile(
    r"(?i)^[A-Z]:\\(?:[^\\/:*?\"<>|\r\n]+\\)*[^\\/:*?\"<>|\r\n]+$"
)
FULL_POSIX_PRIVATE_PATH = re.compile(
    r"^/(?:Users|home)/[^/]+/(?:[^/\r\n]+/)*[^/\r\n]+$"
)


class ReleaseCandidateError(RuntimeError):
    """Fail-closed error for Sprint 19I.18M."""


@dataclass(frozen=True)
class FileDigest:
    path: str
    size: int
    sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReleaseCandidateError(f"JSON inválido: {path}") from exc
    if not isinstance(payload, dict):
        raise ReleaseCandidateError(f"Objeto JSON esperado: {path}")
    return payload


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def find_public_canonical(runtime_root: Path) -> Path:
    candidates = sorted((runtime_root / "canonical").glob("*.jsonl"))
    if len(candidates) != 1:
        raise ReleaseCandidateError(
            f"Canonical público ambiguo/ausente: {[str(x) for x in candidates]}"
        )
    return candidates[0]


def validate_upstream(
    runtime_root: Path,
    acceptance_19l: Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    report_k = load_json(runtime_root / "public_safe_runtime_acceptance.json")
    report_l = load_json(acceptance_19l)
    canonical = find_public_canonical(runtime_root)

    if sha256_file(canonical) != PUBLIC_CANONICAL_SHA256:
        raise ReleaseCandidateError("SHA canonical 19K no aprobado")
    if report_k.get("canonical_sha256") != PUBLIC_CANONICAL_SHA256:
        raise ReleaseCandidateError("Reporte 19K no coincide con canonical aprobado")
    if report_k.get("parent_count") != PUBLIC_PARENT_COUNT:
        raise ReleaseCandidateError("Conteo de parents 19K inesperado")
    if report_k.get("benchmark_passed") is not True:
        raise ReleaseCandidateError("Benchmark 19K no aprobado")
    if report_k.get("blocked_content_absent") is not True:
        raise ReleaseCandidateError("19K no acredita exclusión de contenido bloqueado")

    required_l = {
        "provenance_complete": True,
        "temporal_fail_closed_complete": True,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "legal_local_acceptance": True,
        "publication_legal_acceptance": False,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
    }
    mismatches = {
        key: (report_l.get(key), expected)
        for key, expected in required_l.items()
        if report_l.get(key) is not expected
    }
    if mismatches:
        raise ReleaseCandidateError(f"Gate 19L inesperado: {mismatches}")
    if report_l.get("public_runtime_sha256") != PUBLIC_CANONICAL_SHA256:
        raise ReleaseCandidateError("19L no referencia el canonical público aprobado")
    return report_k, report_l


def _identity_values(value: Any, parent_key: str = "") -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            lowered = key.casefold()
            if lowered in IDENTITY_KEYS and isinstance(child, str):
                found.add(child.casefold())
            elif lowered.startswith("excluded"):
                continue
            else:
                found.update(_identity_values(child, lowered))
    elif isinstance(value, list):
        for child in value:
            found.update(_identity_values(child, parent_key))
    return found


def _string_values(value: Any) -> list[str]:
    strings: list[str] = []
    if isinstance(value, dict):
        for child in value.values():
            strings.extend(_string_values(child))
    elif isinstance(value, list):
        for child in value:
            strings.extend(_string_values(child))
    elif isinstance(value, str):
        strings.append(value)
    return strings


def _audit_json_file(path: Path) -> list[str]:
    violations: list[str] = []
    try:
        if path.suffix.casefold() == ".jsonl":
            values: list[Any] = []
            with path.open("r", encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, start=1):
                    if not line.strip():
                        continue
                    try:
                        values.append(json.loads(line))
                    except json.JSONDecodeError:
                        violations.append(
                            f"{path}: JSONL inválido en línea {line_number}"
                        )
                        return violations
        else:
            values = [json.loads(path.read_text(encoding="utf-8"))]
    except (OSError, json.JSONDecodeError) as exc:
        violations.append(f"{path}: JSON inválido: {exc}")
        return violations

    for value in values:
        blocked = _identity_values(value) & BLOCKED_DOCUMENT_IDS
        if blocked:
            violations.append(
                f"{path}: identidad documental bloqueada: {sorted(blocked)}"
            )
    return violations


def _contains_private_path_in_value(value: Any) -> bool:
    for text in _string_values(value):
        if WINDOWS_ABSOLUTE_PATH.search(text) or POSIX_PRIVATE_PATH.search(text):
            return True
    return False


def _audit_private_paths_json(path: Path) -> bool:
    try:
        if path.suffix.casefold() == ".jsonl":
            with path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    value = json.loads(line)
                    if _contains_private_path_in_value(value):
                        return True
            return False
        value = json.loads(path.read_text(encoding="utf-8"))
        return _contains_private_path_in_value(value)
    except (OSError, json.JSONDecodeError):
        return True


def _basename_for_private_path(value: str) -> str:
    if FULL_WINDOWS_ABSOLUTE_PATH.match(value):
        return PureWindowsPath(value).name
    if FULL_POSIX_PRIVATE_PATH.match(value):
        return PurePosixPath(value).name
    return value


def _sanitize_embedded_private_paths(value: str) -> tuple[str, int]:
    changed = 0

    def replace_windows(match: re.Match[str]) -> str:
        nonlocal changed
        changed += 1
        return PureWindowsPath(match.group(0)).name

    def replace_posix(match: re.Match[str]) -> str:
        nonlocal changed
        changed += 1
        return PurePosixPath(match.group(0)).name

    sanitized = WINDOWS_ABSOLUTE_PATH.sub(replace_windows, value)
    sanitized = POSIX_PRIVATE_PATH.sub(replace_posix, sanitized)
    return sanitized, changed


def _sanitize_value(value: Any) -> tuple[Any, int]:
    if isinstance(value, dict):
        changed = 0
        output: dict[str, Any] = {}
        for key, child in value.items():
            sanitized, count = _sanitize_value(child)
            output[key] = sanitized
            changed += count
        return output, changed
    if isinstance(value, list):
        changed = 0
        output_list: list[Any] = []
        for child in value:
            sanitized, count = _sanitize_value(child)
            output_list.append(sanitized)
            changed += count
        return output_list, changed
    if isinstance(value, str):
        basename_only = _basename_for_private_path(value)
        if basename_only != value:
            return basename_only, 1
        return _sanitize_embedded_private_paths(value)
    return value, 0


def sanitize_json_file(path: Path) -> int:
    if path.suffix.casefold() == ".jsonl":
        changed = 0
        output_lines: list[str] = []
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ReleaseCandidateError(
                        f"JSONL inválido en {path}:{line_number}"
                    ) from exc
                sanitized, count = _sanitize_value(value)
                changed += count
                output_lines.append(
                    json.dumps(
                        sanitized,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                )
        path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")
        return changed

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ReleaseCandidateError(f"JSON inválido: {path}") from exc
    sanitized, changed = _sanitize_value(value)
    path.write_text(
        json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return changed


def sanitize_runtime_private_paths(runtime_dir: Path) -> int:
    changed = 0
    for path in sorted(runtime_dir.rglob("*")):
        if path.is_file() and path.suffix.casefold() in {".json", ".jsonl"}:
            changed += sanitize_json_file(path)
    return changed



def refresh_runtime_inner_manifest(runtime_dir: Path) -> dict[str, int | str]:
    """Recalcula la integridad interna después de sanitizar JSON/JSONL."""

    manifest_path = runtime_dir / "manifest.json"
    chunks_path = runtime_dir / "chunks.jsonl"
    index_path = runtime_dir / "index.faiss"
    for path in (manifest_path, chunks_path, index_path):
        if not path.is_file():
            raise ReleaseCandidateError(
                f"Falta artefacto requerido para integridad interna: {path.name}"
            )

    manifest = load_json(manifest_path)
    manifest["chunks_sha256"] = sha256_file(chunks_path)
    manifest["chunks_bytes"] = chunks_path.stat().st_size
    manifest["index_sha256"] = sha256_file(index_path)
    manifest["index_bytes"] = index_path.stat().st_size
    write_json(manifest_path, manifest)

    try:
        return validate_runtime_inner_integrity(runtime_dir)
    except RuntimeInnerIntegrityError as exc:
        raise ReleaseCandidateError(
            f"Integridad interna del runtime inválida después de sanitización: {exc}"
        ) from exc

def audit_runtime_tree(
    runtime_dir: Path,
    *,
    allow_absolute_private_paths: bool = False,
) -> list[FileDigest]:
    if not runtime_dir.is_dir():
        raise ReleaseCandidateError(f"Runtime ausente: {runtime_dir}")

    violations: list[str] = []
    digests: list[FileDigest] = []
    total_bytes = 0

    for path in sorted(runtime_dir.rglob("*")):
        if path.is_symlink():
            violations.append(f"Symlink no permitido: {path}")
            continue
        if not path.is_file():
            continue

        relative = path.relative_to(runtime_dir).as_posix()
        suffix = path.suffix.casefold()
        if suffix in FORBIDDEN_SUFFIXES:
            violations.append(f"ExtensiÃ³n no permitida: {relative}")

        size = path.stat().st_size
        total_bytes += size
        digests.append(
            FileDigest(
                path=f"runtime/{relative}",
                size=size,
                sha256=sha256_file(path),
            )
        )

        if suffix in {".json", ".jsonl"}:
            violations.extend(_audit_json_file(path))

        if suffix in {".json", ".jsonl", ".txt", ".yaml", ".yml", ".toml"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            if SECRET_PATTERN.search(text):
                violations.append(f"Posible secreto en {relative}")

            if not allow_absolute_private_paths:
                if suffix in {".json", ".jsonl"}:
                    has_private_path = _audit_private_paths_json(path)
                else:
                    has_private_path = bool(
                        WINDOWS_ABSOLUTE_PATH.search(text)
                        or POSIX_PRIVATE_PATH.search(text)
                    )
                if has_private_path:
                    violations.append(f"Ruta local absoluta en {relative}")

    if not digests:
        violations.append("Runtime vacío")
    if total_bytes > MAX_TOTAL_BYTES:
        violations.append(
            f"Runtime excede límite local: {total_bytes} > {MAX_TOTAL_BYTES}"
        )
    if violations:
        raise ReleaseCandidateError(
            "Auditoría de runtime fallÃ³:\n- " + "\n- ".join(violations)
        )
    return digests


def copy_runtime(runtime_dir: Path, staging_dir: Path) -> None:
    target = staging_dir / "runtime"
    shutil.copytree(runtime_dir, target, symlinks=False)


def build_release_metadata(
    report_k: dict[str, Any],
    report_l: dict[str, Any],
    sanitized_private_path_values: int,
) -> dict[str, Any]:
    return {
        "sprint": "19I.18M",
        "artifact_type": "local_public_release_candidate",
        "runtime_scope": "normative_only",
        "canonical_sha256": PUBLIC_CANONICAL_SHA256,
        "parent_count": PUBLIC_PARENT_COUNT,
        "normative_document_count": 14,
        "benchmark_passed": report_k["benchmark_passed"],
        "blocked_content_absent": report_k["blocked_content_absent"],
        "provenance_complete": report_l["provenance_complete"],
        "temporal_fail_closed_complete": report_l[
            "temporal_fail_closed_complete"
        ],
        "temporal_validity_complete": report_l["temporal_validity_complete"],
        "redistribution_human_review_required": report_l[
            "redistribution_human_review_required"
        ],
        "publication_legal_acceptance": report_l[
            "publication_legal_acceptance"
        ],
        "sanitized_private_path_values": sanitized_private_path_values,
        "candidate_only": True,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "automatic_publication_performed": False,
    }


def deterministic_zip(source_dir: Path, output_zip: Path) -> None:
    output_zip.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        output_zip,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(source_dir).as_posix()
            info = zipfile.ZipInfo(relative, date_time=FIXED_ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            info.create_system = 3
            archive.writestr(info, path.read_bytes())


def verify_zip(
    zip_path: Path,
    expected_files: list[FileDigest],
) -> None:
    expected = {item.path: item for item in expected_files}
    with zipfile.ZipFile(zip_path, "r") as archive:
        names = sorted(
            name for name in archive.namelist() if not name.endswith("/")
        )
        if sorted(expected) != names:
            missing = sorted(set(expected) - set(names))
            extra = sorted(set(names) - set(expected))
            raise ReleaseCandidateError(
                f"ZIP con contenido inesperado; missing={missing}; extra={extra}"
            )
        for name in names:
            data = archive.read(name)
            digest = hashlib.sha256(data).hexdigest()
            if digest != expected[name].sha256:
                raise ReleaseCandidateError(f"SHA ZIP divergente: {name}")
            if len(data) != expected[name].size:
                raise ReleaseCandidateError(f"Tamaño ZIP divergente: {name}")


def execute(
    *,
    runtime_root: Path,
    acceptance_19l: Path,
    output_dir: Path,
) -> dict[str, Any]:
    if output_dir.exists():
        raise ReleaseCandidateError(
            f"Output ya existe: {output_dir}; revisar antes de reintentar"
        )

    report_k, report_l = validate_upstream(runtime_root, acceptance_19l)
    runtime_source = runtime_root / "runtime"

    audit_runtime_tree(
        runtime_source,
        allow_absolute_private_paths=True,
    )

    staging = output_dir / "staging"
    staging.mkdir(parents=True)
    copy_runtime(runtime_source, staging)

    sanitized_private_path_values = sanitize_runtime_private_paths(
        staging / "runtime"
    )
    refresh_runtime_inner_manifest(staging / "runtime")

    runtime_digests = audit_runtime_tree(staging / "runtime")

    metadata = build_release_metadata(
        report_k,
        report_l,
        sanitized_private_path_values,
    )
    write_json(staging / "release_metadata.json", metadata)

    release_metadata_path = staging / "release_metadata.json"
    manifest_files = runtime_digests + [
        FileDigest(
            path="release_metadata.json",
            size=release_metadata_path.stat().st_size,
            sha256=sha256_file(release_metadata_path),
        )
    ]
    manifest_payload = {
        "sprint": "19I.18M",
        "candidate_only": True,
        "canonical_sha256": PUBLIC_CANONICAL_SHA256,
        "files": [asdict(item) for item in manifest_files],
    }
    manifest_path = staging / "release_manifest.json"
    write_json(manifest_path, manifest_payload)
    manifest_digest = FileDigest(
        path="release_manifest.json",
        size=manifest_path.stat().st_size,
        sha256=sha256_file(manifest_path),
    )
    expected_zip_files = manifest_files + [manifest_digest]

    zip_path = output_dir / "tributarius-prudens-public-runtime-candidate.zip"
    deterministic_zip(staging, zip_path)
    verify_zip(zip_path, expected_zip_files)

    report = {
        "sprint": "19I.18M",
        "status": "local_release_candidate_built_and_audited",
        "candidate_only": True,
        "canonical_sha256": PUBLIC_CANONICAL_SHA256,
        "parent_count": PUBLIC_PARENT_COUNT,
        "runtime_file_count": len(runtime_digests),
        "zip_file_count": len(expected_zip_files),
        "zip_size": zip_path.stat().st_size,
        "zip_sha256": sha256_file(zip_path),
        "sanitized_private_path_values": sanitized_private_path_values,
        "runtime_integrity_preserved_after_sanitization": True,
        "blocked_document_identity_absent": True,
        "secret_scan_passed": True,
        "absolute_private_path_scan_passed": True,
        "forbidden_extension_scan_passed": True,
        "deterministic_zip_verified": True,
        "technical_release_candidate_acceptance": True,
        "publication_legal_acceptance": False,
        "temporal_validity_complete": False,
        "redistribution_human_review_required": True,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
        "automatic_publication_performed": False,
        "zip_path": str(zip_path),
    }
    write_json(output_dir / "release_candidate_acceptance.json", report)
    return report
