from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.primary_legal_knowledge import PrimaryTaxonomyKind
from app.services.primary_legal_knowledge import (
    PrimaryLegalKnowledgeError,
    load_primary_knowledge_map,
    load_primary_legal_taxonomy,
    validate_primary_taxonomy_links,
)

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "app" / "resources" / "primary_legal_knowledge_map.json"
TAXONOMY_PATH = ROOT / "app" / "resources" / "primary_legal_taxonomy.json"


def test_taxonomy_covers_problem_institution_and_relation() -> None:
    taxonomy = load_primary_legal_taxonomy(TAXONOMY_PATH)
    kinds = {concept.kind for concept in taxonomy.concepts}

    assert kinds == set(PrimaryTaxonomyKind)
    assert len(taxonomy.concepts) == 18


def test_taxonomy_links_only_to_registered_primary_knowledge() -> None:
    knowledge = load_primary_knowledge_map(MAP_PATH)
    taxonomy = load_primary_legal_taxonomy(TAXONOMY_PATH)

    validate_primary_taxonomy_links(knowledge, taxonomy)


def test_every_concept_connects_navigation_with_rbs_and_cbr() -> None:
    taxonomy = load_primary_legal_taxonomy(TAXONOMY_PATH)

    for concept in taxonomy.concepts:
        assert concept.primary_entries
        assert concept.rbs_families
        assert concept.cbr_families
        assert concept.requires_normative_validation is True
        assert concept.can_control_legal_decision is False


def test_taxonomy_supports_multidimensional_fiscal_problem() -> None:
    taxonomy = load_primary_legal_taxonomy(TAXONOMY_PATH)
    by_id = {concept.concept_id: concept for concept in taxonomy.concepts}

    authority = by_id["actuacion_autoridad"]
    defense = by_id["defensa_contribuyente"]
    noncompliance = by_id["incumplimiento_fiscal"]

    activated_entries = set(
        authority.primary_entries + defense.primary_entries + noncompliance.primary_entries
    )
    assert "PRODECON-06" in activated_entries
    assert "PRODECON-08" in activated_entries
    assert "UNAM-VII" in activated_entries
    assert {"R-AUT", "R-DEF", "R-INC"} <= set(
        authority.rbs_families + defense.rbs_families + noncompliance.rbs_families
    )


def test_temporal_relation_keeps_rif_under_normative_validation() -> None:
    taxonomy = load_primary_legal_taxonomy(TAXONOMY_PATH)
    temporal = next(
        concept for concept in taxonomy.concepts if concept.concept_id == "temporalidad_aplicacion"
    )

    assert "PRODECON-12" in temporal.primary_entries
    assert "R-TEM" in temporal.rbs_families
    assert "CBR-TEMPORALIDAD" in temporal.cbr_families
    assert temporal.requires_normative_validation is True


def test_invalid_taxonomy_cannot_reference_unregistered_rbs_family(tmp_path: Path) -> None:
    knowledge = load_primary_knowledge_map(MAP_PATH)
    payload = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    payload["concepts"][0]["rbs_families"].append("R-INVENTADA")
    invalid_path = tmp_path / "invalid_taxonomy.json"
    invalid_path.write_text(json.dumps(payload), encoding="utf-8")
    taxonomy = load_primary_legal_taxonomy(invalid_path)

    with pytest.raises(PrimaryLegalKnowledgeError, match="inconsistente"):
        validate_primary_taxonomy_links(knowledge, taxonomy)
