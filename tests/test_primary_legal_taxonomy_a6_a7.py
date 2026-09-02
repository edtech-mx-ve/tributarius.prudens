from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.domain.primary_legal_knowledge import FiscalProblemInstitutionKind
from app.services.primary_legal_knowledge import (
    PrimaryLegalKnowledgeError,
    load_fiscal_problem_institution_taxonomy,
    load_legal_relation_taxonomy,
    load_primary_knowledge_map,
    validate_a6_a7_links,
)

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "app" / "resources" / "primary_legal_knowledge_map.json"
A6_PATH = ROOT / "app" / "resources" / "fiscal_problem_institution_taxonomy.json"
A7_PATH = ROOT / "app" / "resources" / "legal_relation_taxonomy.json"


def test_a6_separates_problems_and_institutions() -> None:
    taxonomy = load_fiscal_problem_institution_taxonomy(A6_PATH)
    problems = [
        item
        for item in taxonomy.concepts
        if item.kind is FiscalProblemInstitutionKind.PROBLEM
    ]
    institutions = [
        item
        for item in taxonomy.concepts
        if item.kind is FiscalProblemInstitutionKind.INSTITUTION
    ]

    assert len(problems) == 6
    assert len(institutions) == 6
    assert {item.concept_id for item in problems} >= {
        "determinacion_contribucion",
        "actuacion_autoridad",
        "defensa_contribuyente",
    }
    assert {item.concept_id for item in institutions} >= {
        "tributo",
        "obligacion_tributaria",
        "derechos_contribuyente",
        "regimen_isr",
    }


def test_a6_every_taxon_is_multidimensionally_linked() -> None:
    taxonomy = load_fiscal_problem_institution_taxonomy(A6_PATH)
    for concept in taxonomy.concepts:
        assert concept.primary_entries
        assert concept.relation_ids
        assert concept.rbs_families
        assert concept.cbr_families
        assert concept.requires_normative_validation is True
        assert concept.can_control_legal_decision is False


def test_a7_models_general_legal_relations_not_case_conclusions() -> None:
    taxonomy = load_legal_relation_taxonomy(A7_PATH)
    ids = {relation.relation_id for relation in taxonomy.relations}

    assert len(taxonomy.relations) == 12
    assert {
        "REL-SUJ-OBL",
        "REL-HECHO-OBL",
        "REL-AUT-CON",
        "REL-INC-CONSEQ",
        "REL-TEM-APL",
        "REL-REG-REQ",
        "REL-AUT-DEF",
    } <= ids
    for relation in taxonomy.relations:
        assert relation.subject_role
        assert relation.object_role
        assert relation.institution_concepts
        assert relation.requires_normative_validation is True
        assert relation.can_control_legal_decision is False


def test_a6_a7_links_are_closed_over_primary_knowledge() -> None:
    knowledge = load_primary_knowledge_map(MAP_PATH)
    problems = load_fiscal_problem_institution_taxonomy(A6_PATH)
    relations = load_legal_relation_taxonomy(A7_PATH)

    validate_a6_a7_links(knowledge, problems, relations)


def test_resico_style_problem_has_regime_limit_and_temporal_relations() -> None:
    problems = load_fiscal_problem_institution_taxonomy(A6_PATH)
    by_id = {item.concept_id: item for item in problems.concepts}
    regime = by_id["regimen_isr"]

    assert "REL-REG-REQ" in regime.relation_ids
    assert "REL-TEM-APL" in regime.relation_ids
    assert "R-PER" in regime.rbs_families
    assert "R-TRI" in regime.rbs_families
    assert "R-TEM" in regime.rbs_families
    assert "lisr" in regime.candidate_normative_sources


def test_a7_rejects_unknown_problem_link_during_cross_validation(tmp_path: Path) -> None:
    knowledge = load_primary_knowledge_map(MAP_PATH)
    problems = load_fiscal_problem_institution_taxonomy(A6_PATH)
    payload = json.loads(A7_PATH.read_text(encoding="utf-8"))
    payload["relations"][0]["problem_concepts"] = ["problema_inventado"]
    path = tmp_path / "invalid_relations.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    relations = load_legal_relation_taxonomy(path)

    with pytest.raises(PrimaryLegalKnowledgeError, match="A.7 inconsistente"):
        validate_a6_a7_links(knowledge, problems, relations)
