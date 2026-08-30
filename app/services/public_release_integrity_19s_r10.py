from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

EXPECTED_FILES = frozenset(
    {
        "runtime/index.faiss",
        "runtime/chunks.jsonl",
        "runtime/manifest.json",
        "release_metadata.json",
        "release_manifest.json",
    }
)
FIXED_ZIP_TIMESTAMP = (2026, 8, 29, 0, 0, 0)


class PublicReleaseIntegrityError(RuntimeError):
    """Fallo controlado al validar o reparar la integridad del candidato público."""


@dataclass(frozen=True)
class FileDigest:
    path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class RepairSummary:
    output_path: str
    bundle_sha256: str
    chunk_count: int
    chunks_sha256: str
    index_sha256: str
    index_ntotal: int
    vector_dimension: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicReleaseIntegrityError(f"JSON inválido: {path.name}") from exc
    if not isinstance(value, dict):
        raise PublicReleaseIntegrityError(f"Se esperaba objeto JSON: {path.name}")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _safe_extract(candidate: Path, destination: Path) -> None:
    try:
        with zipfile.ZipFile(candidate, "r") as archive:
            names = {name for name in archive.namelist() if not name.endswith("/")}
            if names != EXPECTED_FILES:
                raise PublicReleaseIntegrityError(
                    f"Contrato ZIP inesperado; missing={sorted(EXPECTED_FILES - names)}; "
                    f"extra={sorted(names - EXPECTED_FILES)}"
                )
            root = destination.resolve()
            for info in archive.infolist():
                if info.is_dir():
                    continue
                target = (destination / info.filename).resolve()
                try:
                    target.relative_to(root)
                except ValueError as exc:
                    raise PublicReleaseIntegrityError(
                        f"Ruta ZIP insegura: {info.filename}"
                    ) from exc
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info, "r") as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
    except zipfile.BadZipFile as exc:
        raise PublicReleaseIntegrityError("Candidato ZIP inválido.") from exc


def _count_jsonl(path: Path) -> int:
    count = 0
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line_number, raw in enumerate(stream, start=1):
                if not raw.strip():
                    continue
                try:
                    value = json.loads(raw)
                except json.JSONDecodeError as exc:
                    raise PublicReleaseIntegrityError(
                        f"chunks.jsonl inválido en línea {line_number}"
                    ) from exc
                if not isinstance(value, dict):
                    raise PublicReleaseIntegrityError(
                        f"Chunk no es objeto JSON en línea {line_number}"
                    )
                count += 1
    except (OSError, UnicodeError) as exc:
        raise PublicReleaseIntegrityError("No se pudo leer chunks.jsonl.") from exc
    return count


def _faiss_shape(index_path: Path) -> tuple[int, int]:
    try:
        import faiss
    except ImportError as exc:
        raise PublicReleaseIntegrityError("FAISS no está instalado.") from exc
    try:
        index = faiss.read_index(str(index_path))
    except Exception as exc:  # FAISS expone excepciones nativas no estables.
        raise PublicReleaseIntegrityError("No se pudo abrir index.faiss.") from exc
    return int(index.ntotal), int(index.d)


def _runtime_integrity(runtime: Path) -> tuple[dict[str, Any], FileDigest, FileDigest]:
    manifest_path = runtime / "manifest.json"
    chunks_path = runtime / "chunks.jsonl"
    index_path = runtime / "index.faiss"
    manifest = _load_json(manifest_path)

    chunks = FileDigest(
        "runtime/chunks.jsonl", chunks_path.stat().st_size, sha256_file(chunks_path)
    )
    index = FileDigest(
        "runtime/index.faiss", index_path.stat().st_size, sha256_file(index_path)
    )
    chunk_count = _count_jsonl(chunks_path)
    ntotal, dimension = _faiss_shape(index_path)

    if chunk_count != ntotal:
        raise PublicReleaseIntegrityError(
            f"Desalineación chunks/FAISS: chunks={chunk_count}; ntotal={ntotal}"
        )
    if int(manifest.get("chunk_count", -1)) != chunk_count:
        raise PublicReleaseIntegrityError(
            "manifest.chunk_count no coincide con chunks.jsonl."
        )
    if int(manifest.get("vector_dimension", -1)) != dimension:
        raise PublicReleaseIntegrityError(
            "manifest.vector_dimension no coincide con index.faiss."
        )
    if str(manifest.get("index_sha256", "")).lower() != index.sha256:
        raise PublicReleaseIntegrityError(
            "index.faiss no coincide con el SHA aprobado en manifest.json; "
            "r10 no repara índices."
        )
    if int(manifest.get("index_bytes", -1)) != index.size:
        raise PublicReleaseIntegrityError(
            "index.faiss no coincide con el tamaño aprobado en manifest.json."
        )
    return manifest, chunks, index


def _digest(path: Path, relative: str) -> FileDigest:
    return FileDigest(relative, path.stat().st_size, sha256_file(path))


def _rebuild_outer_manifest(staging: Path) -> None:
    metadata = staging / "release_metadata.json"
    runtime = staging / "runtime"
    payload = _load_json(staging / "release_manifest.json")
    payload["files"] = [
        vars(_digest(runtime / "chunks.jsonl", "runtime/chunks.jsonl")),
        vars(_digest(runtime / "index.faiss", "runtime/index.faiss")),
        vars(_digest(runtime / "manifest.json", "runtime/manifest.json")),
        vars(_digest(metadata, "release_metadata.json")),
    ]
    payload["files"] = sorted(payload["files"], key=lambda item: str(item["path"]))
    _write_json(staging / "release_manifest.json", payload)


def _deterministic_zip(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    if temporary.exists():
        temporary.unlink()
    try:
        with zipfile.ZipFile(
            temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
        ) as archive:
            for path in sorted(source.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(source).as_posix()
                info = zipfile.ZipInfo(relative, date_time=FIXED_ZIP_TIMESTAMP)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                info.create_system = 3
                archive.writestr(info, path.read_bytes())
        temporary.replace(output)
    except OSError as exc:
        if temporary.exists():
            temporary.unlink()
        raise PublicReleaseIntegrityError("No se pudo escribir el candidato reparado.") from exc


def validate_candidate(candidate: Path) -> RepairSummary:
    candidate = candidate.expanduser().resolve()
    if not candidate.is_file():
        raise PublicReleaseIntegrityError(f"Candidato ausente: {candidate}")
    with tempfile.TemporaryDirectory(prefix="tributarius-r10-validate-") as temp:
        staging = Path(temp)
        _safe_extract(candidate, staging)
        manifest, chunks, index = _runtime_integrity(staging / "runtime")
        if str(manifest.get("chunks_sha256", "")).lower() != chunks.sha256:
            raise PublicReleaseIntegrityError(
                "Falló la verificación SHA-256 de chunks."
            )
        if int(manifest.get("chunks_bytes", -1)) != chunks.size:
            raise PublicReleaseIntegrityError(
                "Falló la verificación de tamaño de chunks."
            )

        release_manifest = _load_json(staging / "release_manifest.json")
        raw_files = release_manifest.get("files")
        if not isinstance(raw_files, list):
            raise PublicReleaseIntegrityError("release_manifest.files debe ser lista.")
        expected = {
            str(item.get("path")): item
            for item in raw_files
            if isinstance(item, dict)
        }
        for relative in EXPECTED_FILES - {"release_manifest.json"}:
            item = expected.get(relative)
            if item is None:
                raise PublicReleaseIntegrityError(
                    f"Falta {relative} en release_manifest."
                )
            path = staging / relative
            if item.get("sha256") != sha256_file(path) or item.get("size") != path.stat().st_size:
                raise PublicReleaseIntegrityError(
                    f"Integridad exterior divergente: {relative}"
                )

        ntotal, dimension = _faiss_shape(staging / "runtime/index.faiss")
        return RepairSummary(
            output_path=str(candidate),
            bundle_sha256=sha256_file(candidate),
            chunk_count=_count_jsonl(staging / "runtime/chunks.jsonl"),
            chunks_sha256=chunks.sha256,
            index_sha256=index.sha256,
            index_ntotal=ntotal,
            vector_dimension=dimension,
        )


def repair_candidate(source: Path, output: Path) -> RepairSummary:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if source == output:
        raise PublicReleaseIntegrityError("La salida debe ser distinta del candidato original.")
    if output.exists():
        raise PublicReleaseIntegrityError(
            f"La salida ya existe: {output}; no se sobrescribe automáticamente."
        )

    with tempfile.TemporaryDirectory(prefix="tributarius-r10-repair-") as temp:
        staging = Path(temp)
        _safe_extract(source, staging)
        manifest, chunks, _index = _runtime_integrity(staging / "runtime")

        # Reparación acotada: solo metadatos internos derivados del chunks final.
        manifest["chunks_sha256"] = chunks.sha256
        manifest["chunks_bytes"] = chunks.size
        _write_json(staging / "runtime/manifest.json", manifest)

        # El manifest exterior debe reflejar los bytes finales del runtime.
        _rebuild_outer_manifest(staging)
        _deterministic_zip(staging, output)

    return validate_candidate(output)
