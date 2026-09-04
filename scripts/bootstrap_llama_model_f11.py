from __future__ import annotations

import hashlib
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import unquote, urlparse

from huggingface_hub import hf_hub_download

_MAX_MODEL_BYTES = 1_100_000_000
_CHUNK_SIZE = 1024 * 1024
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


class LlamaModelBootstrapError(RuntimeError):
    """El GGUF F.11 no pudo descargarse o verificarse de forma segura."""


def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise LlamaModelBootstrapError(f"Falta variable de entorno obligatoria: {name}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _huggingface_resolve_target(source: str) -> tuple[str, str, str] | None:
    parsed = urlparse(source)
    if parsed.scheme != "https" or parsed.hostname not in {"huggingface.co", "www.huggingface.co"}:
        return None

    parts = [unquote(part) for part in parsed.path.split("/") if part]
    if len(parts) < 5 or parts[2] != "resolve":
        return None

    repo_id = f"{parts[0]}/{parts[1]}"
    revision = parts[3]
    filename = "/".join(parts[4:])
    if not repo_id or not revision or not filename:
        return None
    return repo_id, revision, filename


def _copy_and_hash(
    source_path: Path,
    temporary: Path,
    *,
    max_bytes: int,
) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    try:
        with source_path.open("rb") as source_handle, temporary.open("wb") as target_handle:
            while True:
                chunk = source_handle.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise LlamaModelBootstrapError(
                        "El GGUF descargado excede el límite F.11."
                    )
                digest.update(chunk)
                target_handle.write(chunk)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise LlamaModelBootstrapError(
            "No fue posible copiar el GGUF descargado por Hugging Face."
        ) from exc

    return digest.hexdigest(), total


def _download_huggingface_model(
    *,
    source: str,
    temporary: Path,
    max_bytes: int,
) -> tuple[str, int]:
    target = _huggingface_resolve_target(source)
    if target is None:
        raise LlamaModelBootstrapError("La URL Hugging Face no tiene formato resolve válido.")

    repo_id, revision, filename = target
    try:
        cached_path = Path(
            hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                revision=revision,
            )
        )
    except Exception as exc:
        temporary.unlink(missing_ok=True)
        raise LlamaModelBootstrapError(
            "Hugging Face Hub no pudo descargar el GGUF F.11."
        ) from exc

    if not cached_path.is_file():
        temporary.unlink(missing_ok=True)
        raise LlamaModelBootstrapError(
            "Hugging Face Hub no devolvió un archivo GGUF utilizable."
        )

    return _copy_and_hash(cached_path, temporary, max_bytes=max_bytes)


def _download_generic_https(
    *,
    source: str,
    temporary: Path,
    timeout_seconds: float,
    max_bytes: int,
) -> tuple[str, int]:
    request = urllib.request.Request(
        source,
        headers={"User-Agent": "Tributarius-Prudens-F11/1.0"},
    )
    digest = hashlib.sha256()
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            raw_length = response.headers.get("Content-Length")
            if raw_length is not None:
                try:
                    announced = int(raw_length)
                except ValueError as exc:
                    raise LlamaModelBootstrapError(
                        "El servidor reportó Content-Length inválido."
                    ) from exc
                if announced <= 0 or announced > max_bytes:
                    raise LlamaModelBootstrapError(
                        "El tamaño anunciado del GGUF excede el límite F.11."
                    )

            with temporary.open("wb") as handle:
                while True:
                    chunk = response.read(_CHUNK_SIZE)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > max_bytes:
                        raise LlamaModelBootstrapError(
                            "El GGUF descargado excede el límite F.11."
                        )
                    digest.update(chunk)
                    handle.write(chunk)
    except (OSError, urllib.error.URLError) as exc:
        temporary.unlink(missing_ok=True)
        raise LlamaModelBootstrapError("Falló la descarga HTTPS del GGUF F.11.") from exc
    except LlamaModelBootstrapError:
        temporary.unlink(missing_ok=True)
        raise

    return digest.hexdigest(), total


def bootstrap_llama_model(
    *,
    source: str,
    expected_sha256: str,
    destination: Path,
    timeout_seconds: float = 600.0,
    max_bytes: int = _MAX_MODEL_BYTES,
) -> tuple[Path, str, int]:
    """Descarga el GGUF, limita tamaño y verifica SHA-256 antes de promoverlo."""

    if not source.startswith("https://"):
        raise LlamaModelBootstrapError("LLAMA_MODEL_URL debe usar HTTPS.")
    expected = expected_sha256.casefold()
    if not _SHA256_RE.fullmatch(expected):
        raise LlamaModelBootstrapError("LLAMA_MODEL_SHA256 no tiene formato válido.")
    if destination.suffix.casefold() != ".gguf":
        raise LlamaModelBootstrapError("LLAMA_MODEL_PATH debe terminar en .gguf.")

    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file():
        actual = _sha256_file(destination)
        size = destination.stat().st_size
        if actual == expected and 0 < size <= max_bytes:
            return destination, actual, size
        destination.unlink()

    temporary = destination.with_suffix(destination.suffix + ".part")
    temporary.unlink(missing_ok=True)

    if _huggingface_resolve_target(source) is not None:
        actual, total = _download_huggingface_model(
            source=source,
            temporary=temporary,
            max_bytes=max_bytes,
        )
    else:
        actual, total = _download_generic_https(
            source=source,
            temporary=temporary,
            timeout_seconds=timeout_seconds,
            max_bytes=max_bytes,
        )

    if total <= 0:
        temporary.unlink(missing_ok=True)
        raise LlamaModelBootstrapError("El GGUF descargado está vacío.")
    if actual != expected:
        temporary.unlink(missing_ok=True)
        raise LlamaModelBootstrapError(
            "El SHA-256 del GGUF descargado no coincide "
            f"(esperado={expected}, obtenido={actual})."
        )

    os.replace(temporary, destination)
    return destination, actual, total


def main() -> int:
    try:
        source = _required_env("LLAMA_MODEL_URL")
        expected_sha256 = _required_env("LLAMA_MODEL_SHA256")
        destination = Path(_required_env("LLAMA_MODEL_PATH"))
        path, actual_sha256, size = bootstrap_llama_model(
            source=source,
            expected_sha256=expected_sha256,
            destination=destination,
        )
    except LlamaModelBootstrapError as exc:
        print(f"ERROR: bootstrap Llama F.11 rechazado: {exc}")
        return 1

    print("OK: F.11; modelo Llama GGUF descargado y verificado")
    print(f"- path={path}")
    print(f"- sha256={actual_sha256}")
    print(f"- size_bytes={size}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
