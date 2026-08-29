import json
from pathlib import Path

import pytest

from app.domain.fiscal_corpus import FiscalDocumentSpec
from app.services.fiscal_corpus_integration import (
    FiscalCorpusIntegrationError,
    load_catalog,
    validate_corpus_inventory,
)

EXPECTED_FILES = {
    "CFF.pdf",
    "CPEUM.pdf",
    "LFDC.pdf",
    "LFISAN.pdf",
    "LFPCA.pdf",
    "LIEPS.pdf",
    "LIF_2026.pdf",
    "LISR.pdf",
    "LIVA.pdf",
    "LOTFJA.pdf",
    "Manual Derecho Fiscal.pdf",
    "Reg_CFF.pdf",
    "Reg_LISR_060516.pdf",
    "Reg_LIVA_250914.pdf",
    "SHCP_281225_01.pdf",
}


def _catalog_path() -> Path:
    return Path("app/resources/fiscal_corpus_15_catalog.json")


def test_real_catalog_has_exactly_fifteen_documents() -> None:
    specs = load_catalog(_catalog_path())
    assert len(specs) == 15
    assert {item.filename for item in specs} == EXPECTED_FILES


def test_catalog_separates_unam_from_normativa() -> None:
    specs = load_catalog(_catalog_path())
    by_name = {item.filename: item for item in specs}
    assert by_name["Manual Derecho Fiscal.pdf"].layer.value == "unam"
    assert all(
        item.layer.value == "normativa"
        for item in specs
        if item.filename != "Manual Derecho Fiscal.pdf"
    )


def test_catalog_has_chunking_profile_for_every_document() -> None:
    specs = load_catalog(_catalog_path())
    assert all(item.chunking_profile.value for item in specs)
    assert (
        next(item for item in specs if item.filename == "SHCP_281225_01.pdf")
        .chunking_profile.value
        == "administrative_rule"
    )


def test_inventory_rejects_missing_pdf(tmp_path: Path) -> None:
    specs = load_catalog(_catalog_path())
    for spec in specs[:-1]:
        (tmp_path / spec.filename).write_bytes(b"%PDF-1.4\n")

    with pytest.raises(FiscalCorpusIntegrationError, match="Faltan PDF"):
        validate_corpus_inventory(tmp_path, specs)


def test_inventory_accepts_required_fifteen_with_extra_prodecon(tmp_path: Path) -> None:
    specs = load_catalog(_catalog_path())
    for spec in specs:
        (tmp_path / spec.filename).write_bytes(b"%PDF-1.4\n")
    (tmp_path / "PRODECON Contribuyente.pdf").write_bytes(b"%PDF-1.4\n")

    inventory = validate_corpus_inventory(tmp_path, specs)
    assert len(inventory) == 15
    assert set(inventory) == {item.canonical_id for item in specs}


def test_spec_rejects_path_traversal() -> None:
    payload = json.loads(_catalog_path().read_text(encoding="utf-8"))[0]
    payload["filename"] = "../CFF.pdf"
    with pytest.raises(ValueError):
        FiscalDocumentSpec.model_validate(payload)
