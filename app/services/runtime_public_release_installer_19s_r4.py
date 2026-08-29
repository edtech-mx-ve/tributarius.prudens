from __future__ import annotations

import hashlib
import shutil
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Final

from app.services import public_release_cold_start_19i18n as cold_start
from app.services import runtime_release_installer as legacy_installer
from app.services.runtime_release_installer import RuntimeReleaseInstallSummary

RuntimeReleaseInstallError = legacy_installer.RuntimeReleaseInstallError

_PUBLIC_RUNTIME_FILES: Final[frozenset[str]] = frozenset(
    {
        "runtime/index.faiss",
        "runtime/chunks.jsonl",
        "runtime/manifest.json",
        "release_metadata.json",
        "release_manifest.json",
    }
)
_RUNTIME_DESTINATION: Final[Path] = Path(
    "deployment/runtime_artifacts_semantic_v2"
)
_TEMPORAL_REGISTRY: Final[Path] = Path(
    "knowledge/temporal/temporal_provenance_registry.json"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise RuntimeReleaseInstallError(f"No se pudo leer {path}") from exc
    return digest.hexdigest()


def _normalized_sha256(value: str) -> str:
    normalized = value.strip().casefold()
    if len(normalized) != 64 or any(
        character not in "0123456789abcdef" for character in normalized
    ):
        raise RuntimeReleaseInstallError(
            "expected_sha256 debe ser SHA-256 hexadecimal."
        )
    return normalized


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
        headers={"User-Agent": "tributarius-prudens-public-runtime/1.0"},
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
    except RuntimeReleaseInstallError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        raise RuntimeReleaseInstallError(
            "No se pudo descargar el bundle público."
        ) from exc


def _materialize_bundle(
    *,
    source: str,
    destination: Path,
    timeout_seconds: float,
    max_bytes: int,
) -> None:
    if source.startswith("https://"):
        _download_https(
            source,
            destination,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes,
        )
        return
    if source.startswith("file://"):
        raise RuntimeReleaseInstallError(
            "file:// no está permitido; use una ruta local explícita en pruebas."
        )
    local_source = Path(source).expanduser().resolve()
    if not local_source.is_file():
        raise RuntimeReleaseInstallError(
            f"No existe bundle local: {local_source}"
        )
    if local_source.stat().st_size > max_bytes:
        raise RuntimeReleaseInstallError(
            "El bundle excede el límite máximo permitido."
        )
    try:
        shutil.copy2(local_source, destination)
    except OSError as exc:
        raise RuntimeReleaseInstallError(
            "No se pudo copiar el bundle local."
        ) from exc


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


def _validate_public_contract(bundle_path: Path, extracted: Path) -> None:
    try:
        members = set(cold_start.validate_candidate_zip(bundle_path))
        if members != set(_PUBLIC_RUNTIME_FILES):
            missing = sorted(set(_PUBLIC_RUNTIME_FILES) - members)
            extra = sorted(members - set(_PUBLIC_RUNTIME_FILES))
            raise RuntimeReleaseInstallError(
                "Contenido público inesperado; "
                f"missing={missing}; extra={extra}"
            )
        cold_start.extract_candidate(bundle_path, extracted)
        cold_start.verify_release_contract(extracted)
    except RuntimeReleaseInstallError:
        raise
    except cold_start.ColdStartError as exc:
        raise RuntimeReleaseInstallError(
            f"Contrato del candidato público inválido: {exc}"
        ) from exc


def install_public_runtime_release(
    *,
    source: str,
    expected_sha256: str,
    project_root: Path,
    timeout_seconds: float = 60.0,
    max_bytes: int = 100_000_000,
) -> RuntimeReleaseInstallSummary:
    """Instala el candidato público 19M sin relajar el contrato legacy 19B."""

    normalized_sha = _normalized_sha256(expected_sha256)
    root = project_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)

    temporal_registry = root / _TEMPORAL_REGISTRY
    if not temporal_registry.is_file():
        raise RuntimeReleaseInstallError(
            "Registro temporal versionado ausente: "
            f"{_TEMPORAL_REGISTRY.as_posix()}"
        )

    with tempfile.TemporaryDirectory(
        prefix="tributarius-public-runtime-"
    ) as temp_dir:
        temp_root = Path(temp_dir)
        bundle_path = temp_root / "runtime.zip"
        _materialize_bundle(
            source=source,
            destination=bundle_path,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes,
        )

        actual_sha = _sha256(bundle_path)
        if actual_sha != normalized_sha:
            raise RuntimeReleaseInstallError(
                "SHA-256 del bundle no coincide con el valor esperado."
            )

        extracted = temp_root / "extracted"
        _validate_public_contract(bundle_path, extracted)

        staged_runtime = extracted / "runtime"
        if not staged_runtime.is_dir():
            raise RuntimeReleaseInstallError(
                "Directorio runtime ausente en candidato público."
            )

        runtime_destination = root / _RUNTIME_DESTINATION
        _replace_tree(staged_runtime, runtime_destination)

        installed_files = tuple(
            sorted(
                (
                    (_RUNTIME_DESTINATION / "index.faiss").as_posix(),
                    (_RUNTIME_DESTINATION / "chunks.jsonl").as_posix(),
                    (_RUNTIME_DESTINATION / "manifest.json").as_posix(),
                    _TEMPORAL_REGISTRY.as_posix(),
                )
            )
        )
        for relative in installed_files:
            if not (root / relative).is_file():
                raise RuntimeReleaseInstallError(
                    f"Archivo esperado no quedó instalado: {relative}"
                )

        return RuntimeReleaseInstallSummary(
            source=source,
            bundle_sha256=normalized_sha,
            bundle_size_bytes=bundle_path.stat().st_size,
            runtime_dir=str(runtime_destination),
            temporal_registry=str(temporal_registry),
            installed_files=installed_files,
        )
