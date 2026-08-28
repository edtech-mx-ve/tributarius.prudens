from __future__ import annotations

import argparse
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

MAX_PUBLIC_FILE_BYTES = 10 * 1024 * 1024

_BLOCKED_SUFFIXES = {
    ".db",
    ".sqlite",
    ".sqlite3",
    ".pem",
    ".key",
    ".p12",
    ".pfx",
    ".jks",
    ".keystore",
    ".gguf",
    ".safetensors",
    ".pt",
    ".pth",
    ".onnx",
    ".ckpt",
    ".zip",
    ".7z",
    ".rar",
}

_BLOCKED_EXACT_NAMES = {
    ".env",
    ".netrc",
}

_BLOCKED_PREFIXES = (
    "knowledge/sources/",
    "knowledge/normalized/",
    "knowledge/chunks/",
    "traceability/exports/",
    "cbr/data/",
    "uploads/",
    "exports/",
    "private/",
    "private_data/",
    "data/private/",
    "data/raw_private/",
)

_ALLOWED_BLOCKED_PREFIX_FILES = {
    "deployment/runtime_artifacts/.gitkeep",
    "deployment/runtime_artifacts/README.md",
    "traceability/exports/.gitkeep",
    "cbr/data/.gitkeep",
}

_ALLOWED_KNOWLEDGE_STRUCTURE = {
    ".gitkeep",
}

_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(
        r"(?i)\b(?:postgres(?:ql)?|mysql)://[^:\s/]+:[^@\s/]+@"
    ),
)

_LOCAL_PATH_PATTERNS = (
    re.compile(r"(?i)\b[A-Z]:\\Users\\[^\\\r\n]+"),
    re.compile(r"(?<![A-Za-z0-9_])/home/[^/\s]+/"),
)

_TEXT_SUFFIXES = {
    ".py",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".jsonl",
    ".md",
    ".html",
    ".css",
    ".js",
    ".txt",
    ".ini",
    ".cfg",
}


@dataclass(frozen=True)
class Finding:
    path: str
    kind: str
    detail: str


class PublishAuditError(RuntimeError):
    """Falla controlada del preflight público."""


def _git_candidates(repo: Path) -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        ],
        cwd=repo,
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise PublishAuditError(
            "No fue posible obtener candidatos Git. "
            f"¿Es un repositorio válido? {stderr}"
        )

    names = [
        item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]
    return [repo / name for name in names]


def _relative(path: Path, repo: Path) -> str:
    return path.relative_to(repo).as_posix()


def _blocked_by_path(relative: str) -> str | None:
    name = Path(relative).name
    suffix = Path(relative).suffix.lower()

    if name in _BLOCKED_EXACT_NAMES:
        return "archivo de configuración/credencial local"
    lowered_name = name.lower()
    if lowered_name.startswith(("credentials", "secrets", "secret")):
        return "nombre asociado a credenciales/secretos"
    if name.startswith(".env.") and name != ".env.example":
        return "variante de .env no pública"
    if suffix in _BLOCKED_SUFFIXES:
        return f"extensión no publicable: {suffix}"

    if relative.startswith("deployment/runtime_artifacts/"):
        if relative not in _ALLOWED_BLOCKED_PREFIX_FILES:
            return "artefacto RAG de runtime"

    if relative.startswith(("knowledge/sources/", "knowledge/normalized/", "knowledge/chunks/")):
        if Path(relative).name not in _ALLOWED_KNOWLEDGE_STRUCTURE:
            return "corpus jurídico-fiscal operativo no revisado"

    for prefix in _BLOCKED_PREFIXES:
        if relative.startswith(prefix) and relative not in _ALLOWED_BLOCKED_PREFIX_FILES:
            if prefix.startswith("knowledge/"):
                continue
            return f"ruta privada/generada: {prefix}"

    return None


def _scan_text(path: Path, relative: str) -> list[Finding]:
    if relative == "scripts/audit_github_publish.py":
        return []
    if path.suffix.lower() not in _TEXT_SUFFIXES and path.name not in {
        ".env.example",
        ".gitignore",
        ".gitattributes",
    }:
        return []

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return [Finding(relative, "text_read_error", "no se pudo validar como UTF-8")]

    findings: list[Finding] = []
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            findings.append(
                Finding(relative, "possible_secret", f"patrón sensible: {pattern.pattern}")
            )
    for pattern in _LOCAL_PATH_PATTERNS:
        if pattern.search(text):
            findings.append(
                Finding(relative, "local_path", "ruta local de usuario detectada")
            )
    return findings


def audit_repository(repo: Path) -> tuple[list[Path], list[Finding]]:
    resolved = repo.expanduser().resolve()
    candidates = _git_candidates(resolved)
    findings: list[Finding] = []

    for path in candidates:
        relative = _relative(path, resolved)
        if not path.is_file():
            continue

        blocked = _blocked_by_path(relative)
        if blocked is not None:
            findings.append(Finding(relative, "blocked_path", blocked))
            continue

        size = path.stat().st_size
        if size > MAX_PUBLIC_FILE_BYTES:
            findings.append(
                Finding(
                    relative,
                    "large_file",
                    f"{size} bytes; máximo público del proyecto={MAX_PUBLIC_FILE_BYTES}",
                )
            )

        findings.extend(_scan_text(path, relative))

    return candidates, findings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audita archivos que Git consideraría para publicación."
    )
    parser.add_argument("--repo", type=Path, default=Path("."))
    args = parser.parse_args()

    try:
        candidates, findings = audit_repository(args.repo)
    except PublishAuditError as exc:
        print(f"ERROR: {exc}")
        return 2

    if findings:
        print(f"ERROR: {len(findings)} hallazgo(s) bloquean la publicación:")
        for finding in findings:
            print(f"- {finding.path}: {finding.kind}: {finding.detail}")
        return 1

    print(
        "OK: preflight GitHub limpio; "
        f"{len(candidates)} archivo(s) candidatos; "
        "sin secretos obvios, corpus privado ni binarios bloqueados."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
