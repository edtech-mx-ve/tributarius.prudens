from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final


class RuntimeReleaseInstallError(RuntimeError):
    """Fallo controlado al instalar un bundle de runtime."""


_EXPECTED_RUNTIME_PREFIX: Final[str] = "deployment/runtime_artifacts_semantic_v2/"
_TEMPORAL_REGISTRY: Final[str] = (
    "knowledge/temporal/temporal_provenance_registry.json"
)
_RELEASE_MANIFEST: Final[str] = "release_manifest.json"
_ALLOWED_FILES: Final[frozenset[str]] = frozenset(
    {
        f"{_EXPECTED_RUNTIME_PREFIX}index.faiss",
        f"{_EXPECTED_RUNTIME_PREFIX}chunks.jsonl",
        f"{_EXPECTED_RUNTIME_PREFIX}manifest.json",
        _TEMPORAL_REGISTRY,
        _RELEASE_MANIFEST,
    }
)


@dataclass(frozen=True)
class RuntimeReleaseInstallSummary:
    source: str
    bundle_sha256: str
    bundle_size_bytes: int
    runtime_dir: str
    temporal_registry: str
    installed_files: tuple[str, ...]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise RuntimeReleaseInstallError(f"No se pudo leer {path}") from exc
    return digest.hexdigest()


def _safe_member_name(name: str) -> str:
    pure = PurePosixPath(name)
    if pure.is_absolute() or ".." in pure.parts or "\\" in name:
        raise RuntimeReleaseInstallError(f"Ruta ZIP insegura: {name!r}")
    normalized = pure.as_posix()
    if normalized not in _ALLOWED_FILES:
        raise RuntimeReleaseInstallError(
            f"Archivo no permitido en bundle: {normalized!r}"
        )
    return normalized


def _validate_bundle(
    bundle_path: Path,
    *,
    expected_sha256: str,
) -> tuple[dict[str, object], tuple[str, ...]]:
    actual_sha256 = _sha256(bundle_path)
    if actual_sha256.casefold() != expected_sha256.casefold():
        raise RuntimeReleaseInstallError(
            "SHA-256 del bundle no coincide con el valor esperado."
        )

    try:
        with zipfile.ZipFile(bundle_path, "r") as archive:
            names = tuple(_safe_member_name(info.filename) for info in archive.infolist())
            if set(names) != set(_ALLOWED_FILES):
                missing = sorted(set(_ALLOWED_FILES) - set(names))
                extra = sorted(set(names) - set(_ALLOWED_FILES))
                raise RuntimeReleaseInstallError(
                    f"Contenido de bundle inesperado; missing={missing}; extra={extra}"
                )

            manifest_raw = archive.read(_RELEASE_MANIFEST)
            manifest = json.loads(manifest_raw.decode("utf-8"))
            if not isinstance(manifest, dict):
                raise RuntimeReleaseInstallError(
                    "release_manifest.json debe ser un objeto."
                )
            files = manifest.get("files")
            if not isinstance(files, dict):
                raise RuntimeReleaseInstallError(
                    "release_manifest.files debe ser un objeto."
                )

            for name, raw_metadata in files.items():
                if not isinstance(name, str) or not isinstance(raw_metadata, dict):
                    raise RuntimeReleaseInstallError(
                        "Entrada inválida en release_manifest.files."
                    )
                normalized = _safe_member_name(name)
                payload = archive.read(normalized)
                expected_file_sha = raw_metadata.get("sha256")
                expected_size = raw_metadata.get("size_bytes")
                if not isinstance(expected_file_sha, str):
                    raise RuntimeReleaseInstallError(
                        f"SHA-256 faltante para {normalized}."
                    )
                if hashlib.sha256(payload).hexdigest() != expected_file_sha:
                    raise RuntimeReleaseInstallError(
                        f"SHA-256 interno inválido: {normalized}"
                    )
                if not isinstance(expected_size, int) or len(payload) != expected_size:
                    raise RuntimeReleaseInstallError(
                        f"Tamaño interno inválido: {normalized}"
                    )
            return manifest, names
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
        KeyError,
    ) as exc:
        raise RuntimeReleaseInstallError("Bundle runtime inválido.") from exc


def _download_https(
    url: str,
    destination: Path,
    *,
    timeout_seconds: float,
    max_bytes: int,
) -> None:
    if not url.startswith("https://"):
        raise RuntimeReleaseInstallError("Solo se permiten URLs HTTPS.")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "tributarius-prudens-runtime-bootstrap/1.0"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            content_length = response.headers.get("Content-Length")
            if content_length is not None and int(content_length) > max_bytes:
                raise RuntimeReleaseInstallError(
                    "El bundle excede el límite máximo permitido."
                )
            total = 0
            with destination.open("wb") as handle:
                while True:
                    block = response.read(1024 * 1024)
                    if not block:
                        break
                    total += len(block)
                    if total > max_bytes:
                        raise RuntimeReleaseInstallError(
                            "El bundle excede el límite máximo permitido."
                        )
                    handle.write(block)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeReleaseInstallError("No se pudo descargar el bundle.") from exc


def _extract_to_staging(bundle_path: Path, staging_root: Path) -> None:
    try:
        with zipfile.ZipFile(bundle_path, "r") as archive:
            for info in archive.infolist():
                name = _safe_member_name(info.filename)
                destination = staging_root / Path(*PurePosixPath(name).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, destination.open("wb") as target:
                    shutil.copyfileobj(source, target)
    except (OSError, zipfile.BadZipFile) as exc:
        raise RuntimeReleaseInstallError("No se pudo extraer el bundle.") from exc


def _replace_tree(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = destination.with_name(f".{destination.name}.backup")
    if backup.exists():
        shutil.rmtree(backup)
    if destination.exists():
        destination.replace(backup)
    try:
        source.replace(destination)
    except OSError as exc:
        if backup.exists() and not destination.exists():
            backup.replace(destination)
        raise RuntimeReleaseInstallError(
            f"No se pudo activar {destination}."
        ) from exc
    if backup.exists():
        shutil.rmtree(backup)


def _replace_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.new")
    shutil.copy2(source, temporary)
    os.replace(temporary, destination)


def install_runtime_release(
    *,
    source: str,
    expected_sha256: str,
    project_root: Path,
    timeout_seconds: float = 60.0,
    max_bytes: int = 100_000_000,
) -> RuntimeReleaseInstallSummary:
    normalized_sha = expected_sha256.strip().casefold()
    if len(normalized_sha) != 64 or any(
        character not in "0123456789abcdef" for character in normalized_sha
    ):
        raise RuntimeReleaseInstallError("expected_sha256 debe ser SHA-256 hexadecimal.")

    root = project_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="tributarius-runtime-") as temp_dir:
        temp_root = Path(temp_dir)
        bundle_path = temp_root / "runtime.zip"

        source_path = Path(source)
        if source.startswith("https://"):
            _download_https(
                source,
                bundle_path,
                timeout_seconds=timeout_seconds,
                max_bytes=max_bytes,
            )
        elif source.startswith("file://"):
            raise RuntimeReleaseInstallError(
                "file:// no está permitido; use una ruta local explícita en pruebas."
            )
        else:
            local_source = source_path.expanduser().resolve()
            if not local_source.is_file():
                raise RuntimeReleaseInstallError(
                    f"No existe bundle local: {local_source}"
                )
            if local_source.stat().st_size > max_bytes:
                raise RuntimeReleaseInstallError(
                    "El bundle excede el límite máximo permitido."
                )
            shutil.copy2(local_source, bundle_path)

        _validate_bundle(
            bundle_path,
            expected_sha256=normalized_sha,
        )
        staging = temp_root / "staging"
        staging.mkdir()
        _extract_to_staging(bundle_path, staging)

        staged_runtime = staging / "deployment/runtime_artifacts_semantic_v2"
        staged_temporal = staging / _TEMPORAL_REGISTRY
        runtime_destination = root / "deployment/runtime_artifacts_semantic_v2"
        temporal_destination = root / _TEMPORAL_REGISTRY

        _replace_tree(staged_runtime, runtime_destination)
        _replace_file(staged_temporal, temporal_destination)

        installed_files = tuple(
            sorted(
                str(path.relative_to(root)).replace(os.sep, "/")
                for path in (
                    runtime_destination / "index.faiss",
                    runtime_destination / "chunks.jsonl",
                    runtime_destination / "manifest.json",
                    temporal_destination,
                )
            )
        )
        return RuntimeReleaseInstallSummary(
            source=source,
            bundle_sha256=normalized_sha,
            bundle_size_bytes=bundle_path.stat().st_size,
            runtime_dir=str(runtime_destination),
            temporal_registry=str(temporal_destination),
            installed_files=installed_files,
        )
