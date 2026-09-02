from pathlib import Path

from app.services.primary_rbs_decision_boundary import (
    load_primary_rbs_decision_boundary_map,
    validate_primary_rbs_decision_boundaries,
)
from app.services.primary_rbs_deduplication import load_primary_rbs_deduplication_map
from app.services.primary_rbs_normative_bindings import (
    load_primary_rbs_normative_binding_map,
)

ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_PATH = ROOT / "app" / "resources" / "primary_rbs_decision_boundary.json"
DEDUP_PATH = ROOT / "app" / "resources" / "primary_rbs_deduplication_map.json"
BINDINGS_PATH = ROOT / "app" / "resources" / "primary_rbs_normative_bindings.json"


def test_b7_classifies_every_b5_relation_once() -> None:
    boundary_map = load_primary_rbs_decision_boundary_map(BOUNDARY_PATH)
    dedup = load_primary_rbs_deduplication_map(DEDUP_PATH)
    bindings = load_primary_rbs_normative_binding_map(BINDINGS_PATH)

    validate_primary_rbs_decision_boundaries(boundary_map, dedup, bindings)

    assert boundary_map.total_boundaries == 18


def test_b7_primary_sources_are_orientation_only() -> None:
    boundary_map = load_primary_rbs_decision_boundary_map(BOUNDARY_PATH)

    assert boundary_map.orientation_is_non_controlling is True
    assert all(
        not boundary.primary_sources_can_control_outcome
        for boundary in boundary_map.boundaries
    )


def test_b7_determination_candidates_require_exact_internal_refs() -> None:
    boundary_map = load_primary_rbs_decision_boundary_map(BOUNDARY_PATH)

    candidates = [
        boundary
        for boundary in boundary_map.boundaries
        if boundary.role.value == "determination_candidate"
    ]
    orientation_only = [
        boundary
        for boundary in boundary_map.boundaries
        if boundary.role.value == "orientation"
    ]

    assert len(candidates) == 10
    assert len(orientation_only) == 8
    assert all(boundary.exact_normative_refs for boundary in candidates)
    assert all(not boundary.exact_normative_refs for boundary in orientation_only)


def test_b7_does_not_enable_executable_determinations() -> None:
    boundary_map = load_primary_rbs_decision_boundary_map(BOUNDARY_PATH)

    assert boundary_map.modifies_production_rules is False
    assert all(
        not boundary.executable_determination_enabled
        for boundary in boundary_map.boundaries
    )
    assert all(
        boundary.requires_normative_validation
        for boundary in boundary_map.boundaries
    )
    assert all(
        boundary.requires_rule_conditions
        for boundary in boundary_map.boundaries
    )


def test_b7_preserves_closed_evidence_principle() -> None:
    boundary_map = load_primary_rbs_decision_boundary_map(BOUNDARY_PATH)

    allowed_primary_prefixes = ("PRODECON-", "UNAM-")
    assert all(
        all(source.startswith(allowed_primary_prefixes) for source in boundary.orientation_sources)
        for boundary in boundary_map.boundaries
    )
    assert boundary_map.determination_requires_internal_normative_evidence is True
