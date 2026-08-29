from __future__ import annotations

import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final


class RuntimeReleasePublicationPlanError(RuntimeError):
    """Fallo controlado al preparar la publicación del runtime."""


_SHA256_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9a-f]{64}$")
_DEFAULT_TAG: Final[str] = "runtime-semantic-v2-19i18"
_DEFAULT_ASSET_NAME: Final[str] = "tributarius-prudens-runtime-semantic-v2.zip"


@dataclass(frozen=True)
class RuntimeReleasePublicationPlan:
    repository: str
    tag: str
    asset_name: str
    asset_path: str
    asset_sha256: str
    asset_size_bytes: int
    release_url: str
    asset_url: str
    release_title: str
    release_notes_path: str
    plan_path: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise RuntimeReleasePublicationPlanError(
            f"No se pudo leer el bundle: {path}"
        ) from exc
    return digest.hexdigest()


def _validate_repository(repository: str) -> str:
    normalized = repository.strip().strip("/")
    parts = normalized.split("/")
    if len(parts) != 2 or not all(parts):
        raise RuntimeReleasePublicationPlanError(
            "repository debe tener formato owner/repo."
        )
    allowed = re.compile(r"^[A-Za-z0-9_.-]+$")
    if not all(allowed.fullmatch(part) for part in parts):
        raise RuntimeReleasePublicationPlanError(
            "repository contiene caracteres no permitidos."
        )
    return normalized


def _validate_tag(tag: str) -> str:
    normalized = tag.strip()
    if not normalized or not re.fullmatch(r"[A-Za-z0-9._-]+", normalized):
        raise RuntimeReleasePublicationPlanError("Tag de release inválido.")
    return normalized


def _read_release_manifest(bundle_path: Path) -> dict[str, object]:
    try:
        with zipfile.ZipFile(bundle_path, "r") as archive:
            payload = json.loads(
                archive.read("release_manifest.json").decode("utf-8")
            )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        zipfile.BadZipFile,
        KeyError,
    ) as exc:
        raise RuntimeReleasePublicationPlanError(
            "El bundle no contiene un release_manifest.json válido."
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeReleasePublicationPlanError(
            "release_manifest.json debe ser un objeto."
        )
    return payload


def build_publication_plan(
    *,
    bundle_path: Path,
    expected_sha256: str,
    repository: str,
    output_dir: Path,
    tag: str = _DEFAULT_TAG,
    asset_name: str = _DEFAULT_ASSET_NAME,
) -> RuntimeReleasePublicationPlan:
    if not bundle_path.is_file():
        raise RuntimeReleasePublicationPlanError(
            f"No existe bundle: {bundle_path}"
        )
    normalized_sha = expected_sha256.strip().casefold()
    if not _SHA256_RE.fullmatch(normalized_sha):
        raise RuntimeReleasePublicationPlanError(
            "expected_sha256 debe ser SHA-256 hexadecimal."
        )
    actual_sha = _sha256(bundle_path)
    if actual_sha != normalized_sha:
        raise RuntimeReleasePublicationPlanError(
            "SHA-256 del bundle no coincide con el aprobado."
        )

    manifest = _read_release_manifest(bundle_path)
    if manifest.get("artifact") != "tributarius-prudens-runtime-semantic-v2":
        raise RuntimeReleasePublicationPlanError(
            "El bundle no corresponde al runtime semántico v2 aprobado."
        )

    normalized_repository = _validate_repository(repository)
    normalized_tag = _validate_tag(tag)
    normalized_asset_name = Path(asset_name).name
    if normalized_asset_name != asset_name or not normalized_asset_name.endswith(".zip"):
        raise RuntimeReleasePublicationPlanError("Nombre de asset inválido.")

    resolved_output = output_dir.expanduser().resolve()
    resolved_output.mkdir(parents=True, exist_ok=True)
    notes_path = resolved_output / "release_notes.md"
    plan_path = resolved_output / "publication_plan.json"

    release_url = (
        f"https://github.com/{normalized_repository}/releases/tag/{normalized_tag}"
    )
    asset_url = (
        f"https://github.com/{normalized_repository}/releases/download/"
        f"{normalized_tag}/{normalized_asset_name}"
    )
    title = "Tributarius prudens — runtime semántico v2"

    notes = f"""# {title}

Artefacto runtime generado localmente y validado antes de publicación.

- Tag: `{normalized_tag}`
- Asset: `{normalized_asset_name}`
- SHA-256: `{normalized_sha}`
- Tamaño: `{bundle_path.stat().st_size}` bytes
- Chunks runtime: `{manifest.get("runtime_chunk_count")}`
- Dimensión vectorial: `{manifest.get("runtime_vector_dimension")}`
- Modelo: `{manifest.get("runtime_model_name")}`
- Guard temporal: `cpeum,liva` permanecen fail-closed.

Este release contiene artefactos de recuperación generados. No contiene los
PDF fuente originales ni modifica la política de vigencia normativa.
"""
    notes_path.write_text(notes, encoding="utf-8")

    plan_payload = {
        "schema_version": "1.0",
        "repository": normalized_repository,
        "tag": normalized_tag,
        "release_title": title,
        "asset_name": normalized_asset_name,
        "asset_path": str(bundle_path.expanduser().resolve()),
        "asset_sha256": normalized_sha,
        "asset_size_bytes": bundle_path.stat().st_size,
        "release_url": release_url,
        "asset_url": asset_url,
        "release_notes_path": str(notes_path),
        "publication_status": "local_plan_only",
        "publish_command_template": (
            f'gh release create "{normalized_tag}" '
            f'"{bundle_path}"#"{normalized_asset_name}" '
            f'--repo "{normalized_repository}" '
            f'--title "{title}" --notes-file "{notes_path}"'
        ),
        "post_publish_required": [
            "verify_public_asset_sha256",
            "set_render_runtime_release_url",
            "rerun_local_release_safety_gate",
        ],
    }
    plan_path.write_text(
        json.dumps(plan_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return RuntimeReleasePublicationPlan(
        repository=normalized_repository,
        tag=normalized_tag,
        asset_name=normalized_asset_name,
        asset_path=str(bundle_path.expanduser().resolve()),
        asset_sha256=normalized_sha,
        asset_size_bytes=bundle_path.stat().st_size,
        release_url=release_url,
        asset_url=asset_url,
        release_title=title,
        release_notes_path=str(notes_path),
        plan_path=str(plan_path),
    )
