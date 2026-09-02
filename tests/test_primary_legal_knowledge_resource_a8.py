from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.primary_legal_knowledge import (
    PrimaryLegalKnowledgeError,
    build_primary_legal_knowledge_resource,
)

ROOT = Path(__file__).resolve().parents[1]
RESOURCE_DIR = ROOT / "app" / "resources"
MANIFEST_PATH = RESOURCE_DIR / "primary_legal_knowledge_manifest.json"


def test_a8_builds_single_versioned_computable_resource() -> None:
    resource = build_primary_legal_knowledge_resource(RESOURCE_DIR, MANIFEST_PATH)

    assert resource.schema_version == "1.0"
    assert resource.knowledge_version == "1.0.0"
    assert len(resource.knowledge_map.entries) == 19
    assert len(resource.problem_institution_taxonomy.concepts) == 12
    assert len(resource.relation_taxonomy.relations) == 12
    assert len(resource.normative_corpus_ids) == 12
    assert len(resource.canonical_sha256) == 64


def test_a8_preserves_closed_evidence_and_non_controller_invariants() -> None:
    resource = build_primary_legal_knowledge_resource(RESOURCE_DIR, MANIFEST_PATH)

    assert resource.requires_normative_validation is True
    assert resource.can_control_legal_decision is False
    assert all(
        entry.requires_normative_validation and not entry.can_control_legal_decision
        for entry in resource.knowledge_map.entries
    )


def test_a8_registers_rbs_and_cbr_families_for_next_blocks() -> None:
    resource = build_primary_legal_knowledge_resource(RESOURCE_DIR, MANIFEST_PATH)

    assert {"R-PER", "R-TRI", "R-OBL", "R-DER", "R-DEF", "R-TEM"} <= set(
        resource.rbs_families
    )
    assert {
        "CBR-PERFIL",
        "CBR-TRIBUTO",
        "CBR-OBLIGACION",
        "CBR-DERECHOS",
        "CBR-DEFENSA",
    } <= set(resource.cbr_families)


def test_a8_hash_is_deterministic_for_same_knowledge_snapshot() -> None:
    first = build_primary_legal_knowledge_resource(RESOURCE_DIR, MANIFEST_PATH)
    second = build_primary_legal_knowledge_resource(RESOURCE_DIR, MANIFEST_PATH)

    assert first.canonical_sha256 == second.canonical_sha256


def test_a8_rejects_manifest_that_drops_a_normative_corpus(tmp_path: Path) -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload["normative_corpus_ids"][-1] = "norma_inventada"
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PrimaryLegalKnowledgeError, match="correspondencia exacta"):
        build_primary_legal_knowledge_resource(RESOURCE_DIR, manifest)


def test_a8_rejects_attempt_to_promote_primary_knowledge_to_controller(
    tmp_path: Path,
) -> None:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    payload["can_control_legal_decision"] = True
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PrimaryLegalKnowledgeError, match="manifiesto A.8 no es válido"):
        build_primary_legal_knowledge_resource(RESOURCE_DIR, manifest)
