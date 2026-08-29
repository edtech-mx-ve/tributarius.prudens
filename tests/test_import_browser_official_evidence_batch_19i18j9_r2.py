from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.runtime_browser_official_batch_import import BatchImportError
from scripts.import_browser_official_evidence_batch_19i18j9 import (
    REQUIRED_CAMERA_DOCUMENTS,
    discover_registry,
)


def _write_registry(path: Path, *, host: str = "www.diputados.gob.mx") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "documents": {
            document_id: {
                "candidate_urls": [
                    f"https://{host}/LeyesBiblio/pdf/{document_id}.pdf"
                ]
            }
            for document_id in REQUIRED_CAMERA_DOCUMENTS
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_discovers_single_compatible_registry(tmp_path: Path) -> None:
    registry = tmp_path / "runtime_official_source_provenance_registry.json"
    _write_registry(registry)
    assert discover_registry(tmp_path) == registry


def test_ignores_unrelated_json(tmp_path: Path) -> None:
    (tmp_path / "unrelated.json").write_text("{}", encoding="utf-8")
    registry = tmp_path / "official_source_registry.json"
    _write_registry(registry)
    assert discover_registry(tmp_path) == registry


def test_rejects_wrong_authority(tmp_path: Path) -> None:
    registry = tmp_path / "official_source_registry.json"
    _write_registry(registry, host="example.com")
    with pytest.raises(BatchImportError, match="No se encontró"):
        discover_registry(tmp_path)


def test_multiple_compatible_registries_require_explicit_selection(
    tmp_path: Path,
) -> None:
    _write_registry(tmp_path / "official_source_registry_a.json")
    _write_registry(tmp_path / "official_source_registry_b.json")
    with pytest.raises(BatchImportError, match="varios registros"):
        discover_registry(tmp_path)
