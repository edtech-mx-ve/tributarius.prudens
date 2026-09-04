from pathlib import Path

from app.domain.jurisprudence import NormRelationType
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_normative_relations import (
    JurisprudenceNormativeLinkBasis,
    JurisprudenceNormativeUnitType,
)
from app.services.jurisprudence_metadata_extraction import (
    extract_jurisprudence_metadata_record,
)
from app.services.jurisprudence_normative_relations import (
    build_jurisprudence_normative_relation_record,
)
from app.web.jurisprudence_session import (
    load_web_jurisprudence_normative_relation_record,
    save_web_jurisprudence_session,
)

SHA = "e" * 64
SESSION_ID = "f" * 32


def _representation(*pages: str) -> JurisprudenceDocumentRepresentation:
    page_models = [
        JurisprudencePage(number=index, text=text, has_extractable_text=True)
        for index, text in enumerate(pages, start=1)
    ]
    full_text = "\n\n".join(pages)
    return JurisprudenceDocumentRepresentation(
        document_id="jurisprudencia-e3-test",
        original_filename="criterio-e3.pdf",
        source_sha256=SHA,
        page_count=len(page_models),
        extracted_characters=len(full_text),
        pages=page_models,
        full_text=full_text,
    )


def _record(document: JurisprudenceDocumentRepresentation):
    metadata = extract_jurisprudence_metadata_record(document)
    return build_jurisprudence_normative_relation_record(
        document, metadata_record=metadata
    )


def test_e3_explicit_interpretation_links_to_closed_corpus_without_applicability() -> None:
    record = _record(
        _representation(
            "Registro digital: 20261234. Texto: Para resolver la controversia se interpreta "
            "el artículo 22 del CFF respecto del saldo a favor."
        )
    )

    assert record.normative_corpus_ids == [
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
    ]
    assert record.mention_count == 1
    mention = record.mentions[0]
    assert mention.candidate_corpus_id == "cff"
    assert mention.candidate_normative_ref == "cff:articulo_22"
    assert mention.relation_type is NormRelationType.INTERPRETS
    assert mention.material_relation_explicit is True
    assert mention.linkage_basis is JurisprudenceNormativeLinkBasis.EXPLICIT_RELATION_LANGUAGE
    assert record.legal_applicability_evaluated is False
    assert mention.can_control_legal_decision is False


def test_e3_plain_norm_mention_is_only_a_citation_not_interpretation() -> None:
    record = _record(
        _representation("El expediente menciona el artículo 28 del Código Fiscal de la Federación.")
    )

    mention = record.mentions[0]
    assert mention.candidate_corpus_id == "cff"
    assert mention.relation_type is NormRelationType.CITES
    assert mention.material_relation_explicit is False
    assert mention.linkage_basis is JurisprudenceNormativeLinkBasis.EXPLICIT_NORMATIVE_MENTION


def test_e3_does_not_create_links_from_thematic_similarity() -> None:
    record = _record(
        _representation(
            "DEVOLUCIÓN DE SALDO A FAVOR. La controversia analiza requisitos fiscales, "
            "sin citar una disposición concreta."
        )
    )

    assert record.mentions == []
    assert record.mention_count == 0
    assert record.thematic_similarity_used is False


def test_e3_records_norm_outside_a8_but_never_promotes_it_to_internal_ref() -> None:
    record = _record(
        _representation(
            "El criterio interpreta el artículo 33 del Reglamento del Código "
            "Fiscal de la Federación."
        )
    )

    assert record.mention_count == 1
    mention = record.mentions[0]
    assert mention.corpus_in_primary_manifest is False
    assert mention.candidate_corpus_id is None
    assert mention.candidate_normative_ref is None
    assert record.unresolved_or_external_count == 1


def test_e3_supports_rmf_rule_as_explicit_internal_normative_unit() -> None:
    record = _record(
        _representation(
            "El criterio interpreta la regla 2.7.1.21 de la RMF 2026 para delimitar el supuesto."
        )
    )

    mention = record.mentions[0]
    assert mention.legal_unit_type is JurisprudenceNormativeUnitType.RULE
    assert mention.legal_unit == "2.7.1.21"
    assert mention.candidate_corpus_id == "rmf_2026"
    assert mention.candidate_normative_ref == "rmf_2026:regla_2_7_1_21"
    assert mention.relation_type is NormRelationType.INTERPRETS


def test_e3_distinguishes_and_conflicts_only_when_source_says_so() -> None:
    record = _record(
        _representation(
            "Este supuesto no resulta aplicable al artículo 69-B del CFF. "
            "Además, existe contradicción con el artículo 5 del CFF."
        )
    )

    assert record.mention_count == 2
    assert record.mentions[0].relation_type is NormRelationType.DISTINGUISHES
    assert record.mentions[1].relation_type is NormRelationType.CONFLICTS
    assert record.explicit_material_relation_count == 2


def test_e3_session_round_trip_preserves_fail_closed_boundaries(tmp_path: Path) -> None:
    document = _representation(
        "Para resolver la controversia se interpreta el artículo 22 del CFF."
    )
    metadata_record = extract_jurisprudence_metadata_record(document)
    relation_record = build_jurisprudence_normative_relation_record(
        document, metadata_record=metadata_record
    )
    (tmp_path / SESSION_ID).mkdir()

    save_web_jurisprudence_session(
        session_id=SESSION_ID,
        representation=document,
        metadata=metadata_record.extracted,
        metadata_record=metadata_record,
        normative_relation_record=relation_record,
        temp_root=tmp_path,
    )
    loaded = load_web_jurisprudence_normative_relation_record(
        SESSION_ID, temp_root=tmp_path
    )

    assert loaded is not None
    assert loaded.source_scope == "session"
    assert loaded.user_attached is True
    assert loaded.temporal_validity_verified is False
    assert loaded.legal_applicability_evaluated is False
    assert loaded.binding_effect_evaluated is False
    assert loaded.can_control_legal_decision is False


def test_e3_does_not_borrow_instrument_from_a_later_sentence() -> None:
    record = _record(
        _representation(
            "Se menciona el artículo 22. Después se interpreta el artículo 28 del CFF."
        )
    )

    assert record.mention_count == 2
    assert record.mentions[0].candidate_corpus_id is None
    assert record.mentions[0].candidate_normative_ref is None
    assert record.mentions[1].candidate_corpus_id == "cff"
    assert record.mentions[1].candidate_normative_ref == "cff:articulo_28"
