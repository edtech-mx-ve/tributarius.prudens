from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.runtime_pdf_differential_diagnostic import (
    normalize_legal_text,
    run_pdf_differential_diagnostic,
)


def _write_json(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _make_pdf(path: Path, body: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.7\n" + body)
    return path


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fixtures(
    tmp_path: Path,
    texts: dict[str, tuple[str, str]],
) -> tuple[dict[str, Path], dict[str, str]]:
    corpus = tmp_path / "corpus"
    evidence = tmp_path / "dist" / "files"
    local_rows = []
    manifest_rows = []
    browser_rows = []
    extracted: dict[str, str] = {}

    for document_id, (local_text, official_text) in texts.items():
        local = _make_pdf(
            corpus / f"local-{document_id}.pdf",
            f"local-{document_id}".encode(),
        )
        official = _make_pdf(
            evidence / f"{document_id}.pdf",
            f"official-{document_id}".encode(),
        )
        local_rows.append(
            {
                "document_id": document_id,
                "source_sha256": _sha(local),
            }
        )
        manifest_rows.append(
            {
                "document_id": document_id,
                "evidence_file": f"files/{document_id}.pdf",
            }
        )
        browser_rows.append(
            {
                "document_id": document_id,
                "status": "official_binary_differs_from_local_pdf",
            }
        )
        extracted[str(local)] = local_text
        extracted[str(official)] = official_text

    local_bridge = _write_json(
        tmp_path / "local_bridge.json", {"documents": local_rows}
    )
    manifest = _write_json(
        tmp_path / "dist" / "manifest.json", {"documents": manifest_rows}
    )
    browser = _write_json(
        tmp_path / "browser_bridge.json", {"documents": browser_rows}
    )
    return (
        {
            "local_bridge_path": local_bridge,
            "browser_manifest_path": manifest,
            "browser_bridge_path": browser,
            "local_corpus_dir": corpus,
            "output_path": tmp_path / "report.json",
        },
        extracted,
    )


def test_normalization_removes_layout_noise() -> None:
    assert normalize_legal_text("ARTÍCULO 1-\nA   Texto") == (
        "artículo 1a texto"
    )


def test_exact_normalized_text_is_classified_as_layout_difference(
    tmp_path: Path,
) -> None:
    paths, extracted = _fixtures(
        tmp_path,
        {
            "lfdc": (
                "Artículo 1. Derecho fiscal.",
                "ARTÍCULO 1.   Derecho fiscal.",
            ),
            "reg_liva_250914": ("Artículo 2. IVA.", "Artículo 2. IVA."),
        },
    )

    def extractor(path: Path) -> tuple[list[str], int]:
        return [extracted[str(path)]], 1

    report = run_pdf_differential_diagnostic(**paths, extractor=extractor)
    assert report["textually_equivalent_documents"] == [
        "lfdc",
        "reg_liva_250914",
    ]
    assert report["corpus_rebuild_required"] is False


def test_material_text_change_requires_rebuild(tmp_path: Path) -> None:
    paths, extracted = _fixtures(
        tmp_path,
        {
            "lfdc": (
                "Artículo 1. A.",
                "Artículo 1. Contenido totalmente distinto.",
            ),
            "reg_liva_250914": ("Artículo 2. IVA.", "Artículo 2. IVA."),
        },
    )

    def extractor(path: Path) -> tuple[list[str], int]:
        return [extracted[str(path)]], 1

    report = run_pdf_differential_diagnostic(**paths, extractor=extractor)
    assert report["material_textual_difference_documents"] == ["lfdc"]
    assert report["corpus_rebuild_required"] is True


def test_report_never_enables_publication(tmp_path: Path) -> None:
    paths, extracted = _fixtures(
        tmp_path,
        {
            "lfdc": ("a", "a"),
            "reg_liva_250914": ("b", "b"),
        },
    )

    def extractor(path: Path) -> tuple[list[str], int]:
        return [extracted[str(path)]], 1

    report = run_pdf_differential_diagnostic(**paths, extractor=extractor)
    assert report["public_release_allowed"] is False
    assert report["official_provenance_promotion_performed"] is False
