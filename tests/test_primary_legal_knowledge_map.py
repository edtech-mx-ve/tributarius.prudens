from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.primary_legal_knowledge import PrimaryManual
from app.services.primary_legal_knowledge import load_primary_knowledge_map

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "app" / "resources" / "primary_legal_knowledge_map.json"
CATALOG_PATH = ROOT / "app" / "resources" / "fiscal_corpus_15_catalog.json"


def test_primary_map_contains_exactly_prodecon_12_and_unam_7() -> None:
    knowledge = load_primary_knowledge_map(MAP_PATH)

    prodecon = [item for item in knowledge.entries if item.manual is PrimaryManual.PRODECON]
    unam = [item for item in knowledge.entries if item.manual is PrimaryManual.UNAM]

    assert len(prodecon) == 12
    assert len(unam) == 7
    assert [item.entry_id for item in prodecon] == [f"PRODECON-{i:02d}" for i in range(1, 13)]
    expected_unam = [
        f"UNAM-{roman}" for roman in ("I", "II", "III", "IV", "V", "VI", "VII")
    ]
    assert [item.entry_id for item in unam] == expected_unam


def test_every_entry_drives_both_rbs_and_cbr_without_controlling_decision() -> None:
    knowledge = load_primary_knowledge_map(MAP_PATH)

    for entry in knowledge.entries:
        assert entry.rbs_families
        assert entry.cbr_families
        assert entry.requires_normative_validation is True
        assert entry.can_control_legal_decision is False


def test_candidate_normative_sources_exist_in_current_normative_catalog() -> None:
    knowledge = load_primary_knowledge_map(MAP_PATH)
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    normative_ids = {item["canonical_id"] for item in catalog if item["layer"] == "normativa"}

    candidates = {
        source
        for entry in knowledge.entries
        for source in entry.candidate_normative_sources
    }

    assert candidates <= normative_ids


def test_rif_is_explicitly_historical_and_temporally_guarded() -> None:
    knowledge = load_primary_knowledge_map(MAP_PATH)
    rif = next(item for item in knowledge.entries if item.entry_id == "PRODECON-12")

    assert rif.historical_content is True
    assert rif.requires_temporal_validation is True
    assert "R-TEM" in rif.rbs_families
    assert "CBR-TEMPORALIDAD" in rif.cbr_families


def test_invalid_map_cannot_promote_manual_to_controlling_source(tmp_path: Path) -> None:
    payload = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    payload["entries"][0]["can_control_legal_decision"] = True
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(Exception, match="no es válida"):
        load_primary_knowledge_map(invalid_path)
