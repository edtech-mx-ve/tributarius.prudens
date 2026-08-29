from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Final

PUBLIC_RUNTIME_SHA256: Final[str] = (
    "4766b49014c5f40aa509b325ddb7268ca7032348559937d2ebae74b0dcefe360"
)

FORBIDDEN_STAGED_PREFIXES: Final[tuple[str, ...]] = (
    "dist/",
    "reports/",
    "knowledge/retrieval_chunks/",
    "knowledge/retrieval_chunks_semantic_v2/",
    "deployment/runtime_artifacts_19f/",
    "deployment/runtime_artifacts_semantic_v2/",
    "knowledge/sources/",
    "knowledge/normalized/",
    "knowledge/chunks/",
    "traceability/exports/",
    "cbr/data/",
)

FORBIDDEN_STAGED_FILENAMES: Final[frozenset[str]] = frozenset(
    {
        ".env",
        "tributarius.db",
        "tributarius.pre_sprint12.db",
        "git-status-prepublish.txt",
    }
)


class PublicationStagingAuditError(RuntimeError):
    """Fallo controlado del gate de staging previo a publicación."""


@dataclass(frozen=True)
class PublicationStagingAudit:
    staged_count: int
    forbidden_paths: tuple[str, ...]
    render_sha_matches_public_candidate: bool
    temporal_registry_staged_or_tracked: bool

    @property
    def accepted(self) -> bool:
        return (
            self.staged_count > 0
            and not self.forbidden_paths
            and self.render_sha_matches_public_candidate
            and self.temporal_registry_staged_or_tracked
        )


def _normalize(path: str) -> str:
    """Normaliza una ruta Git a separadores POSIX."""
    return path.strip().replace("\\", "/")


def find_forbidden_staged_paths(paths: list[str]) -> tuple[str, ...]:
    """Devuelve rutas staged que violan la política de publicación."""
    rejected: list[str] = []
    for raw in paths:
        path = _normalize(raw)
        if not path:
            continue
        if path in FORBIDDEN_STAGED_FILENAMES:
            rejected.append(path)
            continue
        if any(path.startswith(prefix) for prefix in FORBIDDEN_STAGED_PREFIXES):
            rejected.append(path)
    return tuple(sorted(set(rejected)))


def render_uses_public_runtime_sha(render_yaml: str) -> bool:
    """Comprueba que Render fija exactamente el SHA del candidato público."""
    return PUBLIC_RUNTIME_SHA256 in render_yaml


def _git_lines(project_root: Path, *args: str) -> list[str]:
    """Ejecuta Git en modo lectura y devuelve líneas no vacías."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PublicationStagingAuditError(
            f"No se pudo ejecutar git {' '.join(args)}."
        ) from exc
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def audit_publication_staging(project_root: Path) -> PublicationStagingAudit:
    """Audita el índice Git justo antes del commit de publicación."""
    root = project_root.expanduser().resolve()
    render_path = root / "render.yaml"
    if not render_path.is_file():
        raise PublicationStagingAuditError("No existe render.yaml.")

    try:
        render_yaml = render_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise PublicationStagingAuditError("No se pudo leer render.yaml.") from exc

    staged = [
        _normalize(path)
        for path in _git_lines(root, "diff", "--cached", "--name-only")
    ]
    tracked = set(_normalize(path) for path in _git_lines(root, "ls-files"))
    temporal_path = "knowledge/temporal/temporal_provenance_registry.json"
    temporal_registered = temporal_path in set(staged) or temporal_path in tracked

    return PublicationStagingAudit(
        staged_count=len(staged),
        forbidden_paths=find_forbidden_staged_paths(staged),
        render_sha_matches_public_candidate=render_uses_public_runtime_sha(render_yaml),
        temporal_registry_staged_or_tracked=temporal_registered,
    )
