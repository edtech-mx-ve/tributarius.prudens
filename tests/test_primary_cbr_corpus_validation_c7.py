from __future__ import annotations

from pathlib import Path

from app.domain.primary_cbr_corpus_validation import (
    PrimaryCBRCorpusArticleState,
    PrimaryCBRCorpusValidationOutcome,
)
from app.services.primary_cbr_corpus_validation import (
    load_primary_cbr_corpus_validation_report,
    validate_primary_cbr_against_current_corpus,
)
from app.services.primary_cbr_normative_citations import (
    load_primary_cbr_normative_citation_linkage,
)

ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "app" / "resources"


def _load_report():
    return load_primary_cbr_corpus_validation_report(
        RESOURCES / "primary_cbr_corpus_validation.json"
    )


def test_c7_covers_all_37_primary_situations_and_51_links() -> None:
    report = _load_report()

    assert report.source_situation_count == 37
    assert report.explicit_citation_situation_count == 25
    assert report.no_explicit_citation_situation_count == 12
    assert report.article_link_count == 51
    assert report.unique_normative_ref_count == 46
    assert len(report.situations) == 37


def test_c7_article_results_are_closed_and_fail_temporal_validation() -> None:
    report = _load_report()
    links = [item for situation in report.situations for item in situation.article_validations]

    assert report.active_consistent_link_count == 46
    assert report.derogated_link_count == 3
    assert report.content_mismatch_link_count == 2
    assert all(item.article_presence_verified for item in links)
    assert all(item.requires_case_date_validation for item in links)
    assert not any(item.temporal_validity_confirmed for item in links)
    assert not any(item.current_law_verified for item in links)
    assert not any(item.external_legal_evidence_used for item in links)
    assert not any(item.can_support_current_determination for item in links)


def test_c7_detects_derogated_rif_and_liva_article_2() -> None:
    report = _load_report()
    by_ref: dict[str, list] = {}
    for situation in report.situations:
        for link in situation.article_validations:
            by_ref.setdefault(link.candidate_normative_ref, []).append(link)

    assert {item.article_state for item in by_ref["lisr:articulo_111"]} == {
        PrimaryCBRCorpusArticleState.DEROGATED
    }
    assert {item.validation_outcome for item in by_ref["lisr:articulo_111"]} == {
        PrimaryCBRCorpusValidationOutcome.BLOCKED_DEROGATED
    }
    assert by_ref["liva:articulo_2"][0].article_state == PrimaryCBRCorpusArticleState.DEROGATED


def test_c7_detects_two_material_citation_mismatches() -> None:
    report = _load_report()
    mismatches = {
        link.candidate_normative_ref
        for situation in report.situations
        for link in situation.article_validations
        if link.article_state == PrimaryCBRCorpusArticleState.CONTENT_MISMATCH
    }

    assert mismatches == {"cff:articulo_93", "lisr:articulo_35"}


def test_c7_only_validates_situations_with_materially_supported_citations() -> None:
    report = _load_report()
    validated = {item.situation_id for item in report.situations if item.corpus_validated}
    blocked = {
        item.situation_id
        for item in report.situations
        if item.validation_outcome
        in {
            PrimaryCBRCorpusValidationOutcome.BLOCKED_DEROGATED,
            PrimaryCBRCorpusValidationOutcome.BLOCKED_CONTENT_MISMATCH,
        }
    }

    assert report.corpus_validated_situation_count == 20
    assert report.blocked_situation_count == 5
    assert blocked == {
        "P-CBR-SIT-010",
        "P-CBR-SIT-019",
        "P-CBR-SIT-023",
        "U-CBR-SIT-008",
        "U-CBR-SIT-010",
    }
    assert len(validated) == 20


def test_c7_validates_against_c6_manifest_catalog_and_temporal_registry() -> None:
    report = _load_report()
    c6 = load_primary_cbr_normative_citation_linkage(
        RESOURCES / "primary_cbr_normative_citations.json"
    )

    validate_primary_cbr_against_current_corpus(
        report,
        c6,
        primary_manifest_path=RESOURCES / "primary_legal_knowledge_manifest.json",
        fiscal_catalog_path=RESOURCES / "fiscal_corpus_15_catalog.json",
        temporal_registry_path=ROOT
        / "knowledge"
        / "temporal"
        / "temporal_provenance_registry.json",
    )

    assert report.document_wide_temporal_blocks == ["cpeum", "liva"]
    assert report.temporal_registry_source_sprint == "19I.13"
    assert not report.validates_current_law_for_case
    assert not report.assigns_cbr_families
    assert not report.creates_operational_cases
    assert not report.modifies_existing_cbr_engine
    assert not report.can_control_legal_decision
