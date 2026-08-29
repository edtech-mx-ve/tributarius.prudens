from __future__ import annotations

import hashlib
import importlib
import json
import re
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

TARGET_DOCUMENTS = ("lfdc", "reg_liva_250914")
MAX_PDF_BYTES = 50 * 1024 * 1024

LOCAL_FILENAME_ALIASES: dict[str, tuple[str, ...]] = {
    "lfdc": ("LFDC.pdf", "lfdc.pdf"),
    "reg_liva_250914": (
        "Reg_LIVA_250914.pdf",
        "reg_liva_250914.pdf",
        "REG_LIVA_250914.pdf",
    ),
}


class PdfDifferentialError(RuntimeError):
    """Raised when a differential PDF audit cannot be completed safely."""


@dataclass(frozen=True)
class PdfTextProfile:
    sha256: str
    size_bytes: int
    page_count: int
    extracted_characters: int
    normalized_characters: int
    normalized_text_sha256: str


@dataclass(frozen=True)
class DifferentialDecision:
    document_id: str
    local_pdf: str
    official_pdf: str
    local: PdfTextProfile
    official: PdfTextProfile
    exact_binary_match: bool
    exact_normalized_text_match: bool
    text_similarity: float
    page_count_equal: bool
    classification: str
    requires_corpus_rebuild: bool
    publication_ready: bool


TextExtractor = Callable[[Path], tuple[list[str], int]]


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PdfDifferentialError(f"No se pudo leer JSON válido: {path}") from exc
    if not isinstance(payload, dict):
        raise PdfDifferentialError(f"Se esperaba objeto JSON: {path}")
    return payload


def _walk_dicts(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_dicts(child)


def _doc_id(row: dict[str, Any]) -> str | None:
    for key in ("document_id", "id", "doc_id"):
        value = row.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _recursive_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in _walk_dicts(payload):
        document_id = _doc_id(row)
        if document_id is not None:
            current = result.get(document_id, {})
            merged = dict(current)
            merged.update(row)
            result[document_id] = merged
    return result


def _string_set(payload: dict[str, Any], keys: tuple[str, ...]) -> set[str]:
    values: set[str] = set()
    for key in keys:
        raw = payload.get(key)
        if isinstance(raw, list):
            values.update(item for item in raw if isinstance(item, str))
    return values


def _first_str(row: dict[str, Any] | None, keys: tuple[str, ...]) -> str | None:
    if row is None:
        return None
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_pdf(path: Path) -> None:
    if not path.is_file():
        raise PdfDifferentialError(f"No existe PDF regular: {path}")
    size = path.stat().st_size
    if size <= 0 or size > MAX_PDF_BYTES:
        raise PdfDifferentialError(f"Tamaño PDF fuera de rango: {path} ({size})")
    with path.open("rb") as stream:
        if stream.read(5) != b"%PDF-":
            raise PdfDifferentialError(f"Firma %PDF- ausente: {path}")


def _extract_with_dynamic_backend(path: Path) -> tuple[list[str], int]:
    errors: list[str] = []

    try:
        module = importlib.import_module("pypdf")
        reader = module.PdfReader(str(path))
        pages = [(page.extract_text() or "") for page in reader.pages]
        return pages, len(reader.pages)
    except Exception as exc:  # pragma: no cover
        errors.append(f"pypdf={type(exc).__name__}: {exc}")

    try:
        module = importlib.import_module("PyPDF2")
        reader = module.PdfReader(str(path))
        pages = [(page.extract_text() or "") for page in reader.pages]
        return pages, len(reader.pages)
    except Exception as exc:  # pragma: no cover
        errors.append(f"PyPDF2={type(exc).__name__}: {exc}")

    raise PdfDifferentialError(
        "No fue posible extraer texto PDF con backends disponibles: "
        + " | ".join(errors)
    )


def normalize_legal_text(text: str) -> str:
    value = text.replace("\u00ad", "")
    value = re.sub(r"-\s*\n\s*(?=\w)", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.casefold().strip()


def _token_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    left_tokens = left.split()
    right_tokens = right.split()
    if not left_tokens and not right_tokens:
        return 1.0
    if not left_tokens or not right_tokens:
        return 0.0

    l_count = Counter(left_tokens)
    r_count = Counter(right_tokens)
    overlap = sum((l_count & r_count).values())
    return (2.0 * overlap) / (len(left_tokens) + len(right_tokens))


def _profile(path: Path, extractor: TextExtractor) -> tuple[PdfTextProfile, str]:
    _validate_pdf(path)
    pages, page_count = extractor(path)
    text = "\n".join(pages)
    normalized = normalize_legal_text(text)
    profile = PdfTextProfile(
        sha256=_sha256(path),
        size_bytes=path.stat().st_size,
        page_count=page_count,
        extracted_characters=len(text),
        normalized_characters=len(normalized),
        normalized_text_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
    )
    return profile, normalized


def _resolve_manifest_pdf(
    manifest_path: Path,
    row: dict[str, Any] | None,
    document_id: str,
) -> Path:
    raw = _first_str(
        row,
        (
            "evidence_file",
            "evidence_path",
            "file",
            "relative_path",
            "path",
        ),
    )
    if raw is None:
        candidate = manifest_path.parent / "files" / f"{document_id}.pdf"
    else:
        candidate = Path(raw)
        if not candidate.is_absolute():
            candidate = manifest_path.parent / candidate
    return candidate


def _expected_local_sha(
    local_row: dict[str, Any] | None,
    browser_row: dict[str, Any] | None,
) -> str | None:
    keys = (
        "source_sha256",
        "local_sha256",
        "local_source_sha256",
        "source_pdf_sha256",
        "sha256",
        "resolved_sha256",
    )
    return _first_str(local_row, keys) or _first_str(browser_row, keys)


def _resolve_local_pdf(
    bridge_path: Path,
    local_row: dict[str, Any] | None,
    browser_row: dict[str, Any] | None,
    document_id: str,
    local_corpus_dir: Path | None,
) -> Path:
    raw = _first_str(
        local_row,
        (
            "local_source_path",
            "resolved_path",
            "source_path",
            "matched_file",
            "source_file",
            "local_pdf",
            "pdf_path",
        ),
    )
    if raw is not None:
        candidate = Path(raw)
        if candidate.is_absolute() and candidate.exists():
            return candidate
        repo_root = bridge_path.parents[2]
        repo_relative = repo_root / candidate
        if repo_relative.exists():
            return repo_relative

    if local_corpus_dir is None:
        raise PdfDifferentialError(
            f"No se pudo resolver PDF local para {document_id}; "
            "falta --local-corpus-dir."
        )

    if not local_corpus_dir.is_dir():
        raise PdfDifferentialError(
            f"Directorio de corpus local inválido: {local_corpus_dir}"
        )

    all_pdfs = list(local_corpus_dir.rglob("*.pdf"))
    wanted_sha = _expected_local_sha(local_row, browser_row)
    if wanted_sha is not None:
        wanted_sha = wanted_sha.casefold()
        matches = [
            path for path in all_pdfs if _sha256(path).casefold() == wanted_sha
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise PdfDifferentialError(
                f"SHA local ambiguo para {document_id}: {len(matches)} archivos"
            )

    aliases = LOCAL_FILENAME_ALIASES.get(document_id, ())
    alias_matches = [
        path
        for path in all_pdfs
        if path.name.casefold() in {name.casefold() for name in aliases}
    ]
    if len(alias_matches) == 1:
        candidate = alias_matches[0]
        if wanted_sha is not None and _sha256(candidate).casefold() != wanted_sha:
            raise PdfDifferentialError(
                f"El archivo candidato {candidate} no coincide con el SHA local "
                f"registrado para {document_id}."
            )
        return candidate
    if len(alias_matches) > 1:
        raise PdfDifferentialError(
            f"Nombre local ambiguo para {document_id}: {len(alias_matches)} archivos"
        )

    raise PdfDifferentialError(
        f"No se pudo resolver PDF local para {document_id}. "
        f"Archivos PDF observados en corpus={len(all_pdfs)}."
    )


def _is_marked_binary_difference(
    payload: dict[str, Any],
    document_id: str,
    row: dict[str, Any] | None,
) -> bool:
    differing = _string_set(
        payload,
        (
            "differing_binary_documents",
            "blocked_documents",
        ),
    )
    if document_id in differing:
        return True

    status = _first_str(row, ("status", "comparison_status"))
    return status == "official_binary_differs_from_local_pdf"


def run_pdf_differential_diagnostic(
    *,
    local_bridge_path: Path,
    browser_manifest_path: Path,
    browser_bridge_path: Path,
    output_path: Path,
    local_corpus_dir: Path | None = None,
    extractor: TextExtractor | None = None,
) -> dict[str, Any]:
    local_bridge = _load_json(local_bridge_path)
    browser_manifest = _load_json(browser_manifest_path)
    browser_bridge = _load_json(browser_bridge_path)

    local_index = _recursive_index(local_bridge)
    manifest_index = _recursive_index(browser_manifest)
    browser_index = _recursive_index(browser_bridge)
    use_extractor = extractor or _extract_with_dynamic_backend

    decisions: list[DifferentialDecision] = []

    for document_id in TARGET_DOCUMENTS:
        browser_row = browser_index.get(document_id)
        if not _is_marked_binary_difference(
            browser_bridge,
            document_id,
            browser_row,
        ):
            raise PdfDifferentialError(
                f"{document_id} no está marcado como diferencia binaria en J.7"
            )

        local_pdf = _resolve_local_pdf(
            local_bridge_path,
            local_index.get(document_id),
            browser_row,
            document_id,
            local_corpus_dir,
        )
        official_pdf = _resolve_manifest_pdf(
            browser_manifest_path,
            manifest_index.get(document_id),
            document_id,
        )

        local_profile, local_text = _profile(local_pdf, use_extractor)
        official_profile, official_text = _profile(official_pdf, use_extractor)

        binary_equal = local_profile.sha256 == official_profile.sha256
        text_equal = (
            local_profile.normalized_text_sha256
            == official_profile.normalized_text_sha256
        )
        similarity = _token_similarity(local_text, official_text)
        pages_equal = local_profile.page_count == official_profile.page_count

        if binary_equal:
            classification = "unexpected_binary_identity"
            rebuild = False
        elif text_equal:
            classification = "binary_or_layout_difference_textually_equivalent"
            rebuild = False
        elif similarity >= 0.9995:
            classification = "near_textual_equivalence_requires_manual_review"
            rebuild = False
        else:
            classification = "material_textual_difference_detected"
            rebuild = True

        decisions.append(
            DifferentialDecision(
                document_id=document_id,
                local_pdf=str(local_pdf),
                official_pdf=str(official_pdf),
                local=local_profile,
                official=official_profile,
                exact_binary_match=binary_equal,
                exact_normalized_text_match=text_equal,
                text_similarity=round(similarity, 8),
                page_count_equal=pages_equal,
                classification=classification,
                requires_corpus_rebuild=rebuild,
                publication_ready=False,
            )
        )

    material = [
        row.document_id for row in decisions if row.requires_corpus_rebuild
    ]
    equivalent = [
        row.document_id
        for row in decisions
        if row.classification
        == "binary_or_layout_difference_textually_equivalent"
    ]
    manual = [
        row.document_id
        for row in decisions
        if row.classification
        == "near_textual_equivalence_requires_manual_review"
    ]

    report = {
        "sprint": "19I.18J.11",
        "mode": "diagnostic_fail_closed",
        "observed_documents": len(decisions),
        "textually_equivalent_documents": equivalent,
        "manual_review_documents": manual,
        "material_textual_difference_documents": material,
        "documents": [asdict(row) for row in decisions],
        "corpus_rebuild_required": bool(material),
        "automatic_corpus_mutation_performed": False,
        "official_provenance_promotion_performed": False,
        "public_release_allowed": False,
        "git_push_allowed": False,
        "github_release_allowed": False,
        "render_deploy_allowed": False,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return report
