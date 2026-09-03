from pathlib import Path

from app.services.primary_cbr_normative_citations import (
    load_primary_cbr_normative_citation_linkage,
    validate_primary_cbr_normative_citation_linkage,
)
from app.services.primary_cbr_problem_institution import (
    load_primary_cbr_problem_institution_classification,
)
from app.services.primary_cbr_source_situations import load_primary_cbr_situation_extraction
from app.services.primary_legal_knowledge import load_primary_knowledge_manifest

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"


def _load_inputs():
    linkage = load_primary_cbr_normative_citation_linkage(
        RESOURCES / "primary_cbr_normative_citations.json"
    )
    classification = load_primary_cbr_problem_institution_classification(
        RESOURCES / "primary_cbr_problem_institution.json"
    )
    prodecon = load_primary_cbr_situation_extraction(
        RESOURCES / "prodecon_cbr_situations.json"
    )
    unam = load_primary_cbr_situation_extraction(
        RESOURCES / "unam_cbr_practical_cases.json"
    )
    manifest = load_primary_knowledge_manifest(
        RESOURCES / "primary_legal_knowledge_manifest.json"
    )
    return linkage, classification, prodecon, unam, manifest


def test_c6_links_exactly_the_37_cbr_source_situations() -> None:
    linkage, classification, prodecon, unam, manifest = _load_inputs()

    validate_primary_cbr_normative_citation_linkage(
        linkage,
        classification,
        prodecon,
        unam,
        manifest,
    )

    assert linkage.source_situation_count == 37
    assert linkage.linked_situation_count == 25
    assert linkage.unlinked_situation_count == 12
    assert linkage.article_link_count == 51
    assert linkage.unique_candidate_normative_ref_count == 46


def test_c6_normalizes_only_explicit_source_citations_to_a8_candidate_corpora() -> None:
    linkage, _, prodecon, unam, manifest = _load_inputs()
    source_items = {
        item.situation_id: item for item in [*prodecon.situations, *unam.situations]
    }
    manifest_ids = set(manifest.normative_corpus_ids)

    assert linkage.candidate_corpus_ids == ["cff", "cpeum", "lfdc", "lisr", "liva"]
    for item in linkage.situations:
        for link in item.article_links:
            assert link.source_page in source_items[item.situation_id].source_pages
            assert link.candidate_corpus_id in manifest_ids
            assert link.source_citation_only is True
            assert link.linkage_basis.value == "explicit_source_citation"
            expected_article = link.article.lower().replace("-", "_")
            assert link.candidate_normative_ref == (
                f"{link.candidate_corpus_id}:articulo_{expected_article}"
            )


def test_c6_preserves_c5_classification_and_similarity_seed_unchanged() -> None:
    linkage, classification, _, _, _ = _load_inputs()
    previous = {item.situation_id: item for item in classification.classifications}

    for item in linkage.situations:
        c5 = previous[item.situation_id]
        assert item.primary_problem_id == c5.primary_problem_id
        assert item.primary_institution_id == c5.primary_institution_id
        assert item.similarity_seed == c5.similarity_seed
        assert item.unresolved_required_case_fields == c5.unresolved_required_case_fields


def test_c6_preserves_source_citation_anomalies_for_c7_instead_of_correcting_them() -> None:
    linkage, _, _, _, _ = _load_inputs()
    items = {item.situation_id: item for item in linkage.situations}

    prodecon_salary = items["P-CBR-SIT-019"].article_links
    prodecon_refs = [
        (link.candidate_corpus_id, link.article, link.qualifier)
        for link in prodecon_salary
    ]
    assert prodecon_refs == [("cff", "93", "fracción I")]
    assert prodecon_salary[0].source_instrument_as_printed == "CFF"

    unam_rent = items["U-CBR-SIT-010"].article_links
    assert [(link.candidate_corpus_id, link.article) for link in unam_rent] == [
        ("lisr", "35"),
        ("lisr", "116"),
    ]
    assert all(link.article_content_verified is False for link in unam_rent)


def test_c6_records_no_citation_without_inventing_article_links() -> None:
    linkage, _, _, _, _ = _load_inputs()
    unlinked = {item.situation_id for item in linkage.situations if not item.article_links}

    assert unlinked == {
        "P-CBR-SIT-002",
        "P-CBR-SIT-003",
        "P-CBR-SIT-007",
        "P-CBR-SIT-008",
        "P-CBR-SIT-009",
        "P-CBR-SIT-016",
        "P-CBR-SIT-017",
        "P-CBR-SIT-020",
        "P-CBR-SIT-022",
        "P-CBR-SIT-024",
        "U-CBR-SIT-004",
        "U-CBR-SIT-012",
    }
    assert all(
        item.no_explicit_article_reason
        for item in linkage.situations
        if item.situation_id in unlinked
    )


def test_c6_defers_corpus_vigency_families_and_operation_to_later_subblocks() -> None:
    linkage, _, _, _, _ = _load_inputs()

    assert linkage.links_normative_articles is True
    assert linkage.verifies_article_presence is False
    assert linkage.validates_current_law is False
    assert linkage.assigns_cbr_families is False
    assert linkage.creates_operational_cases is False
    assert linkage.modifies_existing_cbr_engine is False
    assert linkage.source_is_normative_authority is False
    assert linkage.can_control_legal_decision is False

    assert all(item.normative_articles_linked is True for item in linkage.situations)
    assert all(item.corpus_validated is False for item in linkage.situations)
    assert all(item.cbr_family_assigned is False for item in linkage.situations)
    assert all(item.operational_case_created is False for item in linkage.situations)
    assert all(
        link.article_presence_verified is False
        and link.article_content_verified is False
        and link.current_law_verified is False
        for item in linkage.situations
        for link in item.article_links
    )
