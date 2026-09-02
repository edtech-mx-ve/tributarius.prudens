from pathlib import Path

from app.services.primary_rbs_deduplication import load_primary_rbs_deduplication_map
from app.services.primary_rbs_normative_bindings import (
    load_primary_rbs_normative_binding_map,
    validate_primary_rbs_normative_bindings,
)

ROOT = Path(__file__).resolve().parents[1]
BINDINGS_PATH = ROOT / "app" / "resources" / "primary_rbs_normative_bindings.json"
DEDUP_PATH = ROOT / "app" / "resources" / "primary_rbs_deduplication_map.json"

ALLOWED_NORMATIVE_SOURCES = {
    "cff",
    "cpeum",
    "lfdc",
    "lfisan",
    "lfpca",
    "lieps",
    "lisr",
    "liva",
    "lotfja",
    "reg_lisr_060516",
    "reg_liva_250914",
    "rmf_2026",
}


def test_b6_binds_every_b5_relation_once() -> None:
    bindings = load_primary_rbs_normative_binding_map(BINDINGS_PATH)
    dedup = load_primary_rbs_deduplication_map(DEDUP_PATH)

    validate_primary_rbs_normative_bindings(
        bindings,
        dedup,
        ALLOWED_NORMATIVE_SOURCES,
    )

    assert bindings.total_bindings == 18
    assert {binding.relation_id for binding in bindings.bindings} == {
        relation.canonical_id for relation in dedup.relations
    }


def test_b6_stays_inside_closed_normative_corpus() -> None:
    bindings = load_primary_rbs_normative_binding_map(BINDINGS_PATH)

    assert all(
        set(binding.normative_source_ids) <= ALLOWED_NORMATIVE_SOURCES
        for binding in bindings.bindings
    )
    assert all(
        exact_ref.split(":", 1)[0] in ALLOWED_NORMATIVE_SOURCES
        for binding in bindings.bindings
        for exact_ref in binding.exact_normative_refs
    )


def test_b6_reuses_only_known_exact_refs_at_this_stage() -> None:
    bindings = load_primary_rbs_normative_binding_map(BINDINGS_PATH)
    exact_refs = {
        exact_ref
        for binding in bindings.bindings
        for exact_ref in binding.exact_normative_refs
    }

    assert exact_refs == {
        "cff:articulo_1",
        "cff:articulo_2",
        "lfdc:articulo_2",
        "lisr:articulo_94",
        "lisr:articulo_100",
        "lisr:articulo_110",
    }


def test_b6_does_not_create_or_modify_executable_rules() -> None:
    bindings = load_primary_rbs_normative_binding_map(BINDINGS_PATH)

    assert bindings.modifies_production_rules is False
    assert all(not binding.creates_executable_rule for binding in bindings.bindings)
    assert all(not binding.can_control_legal_decision for binding in bindings.bindings)


def test_b6_defers_currentness_validation_to_b8() -> None:
    bindings = load_primary_rbs_normative_binding_map(BINDINGS_PATH)

    assert all(
        binding.requires_current_corpus_validation
        for binding in bindings.bindings
    )
