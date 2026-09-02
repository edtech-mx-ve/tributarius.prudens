import pytest

from app.domain.jurisprudence import JurisprudenceStatus, NormRelationType
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.domain.jurisprudence_session_retrieval import SessionJurisprudenceHit
from app.services.jurisprudence_applicability import (
    JurisprudenceApplicabilityError,
    assess_session_jurisprudence_applicability,
)

SHA256 = "c" * 64


def _document() -> JurisprudenceDocumentRepresentation:
    text = "Devolución de saldo a favor. Artículo 22 del CFF."
    return JurisprudenceDocumentRepresentation(
        document_id="jurisprudencia-aplicabilidad",
        original_filename="criterio.pdf",
        source_sha256=SHA256,
        page_count=1,
        extracted_characters=len(text),
        pages=[JurisprudencePage(number=1, text=text, has_extractable_text=True)],
        full_text=text,
    )


def _hit() -> SessionJurisprudenceHit:
    return SessionJurisprudenceHit(
        rank=1,
        score=1.0,
        document_id="jurisprudencia-aplicabilidad",
        original_filename="criterio.pdf",
        source_sha256=SHA256,
        page_number=1,
        text="Devolución de saldo a favor. Artículo 22 del CFF.",
    )


def _metadata(**overrides: object) -> JurisprudenceExtractedMetadata:
    payload: dict[str, object] = {
        "identifier": "20261234",
        "title": "DEVOLUCIÓN DE SALDO A FAVOR.",
        "court_or_body": "Primera Sala",
        "status": JurisprudenceStatus.UNKNOWN,
        "matter": "Administrativa",
        "related_normative_refs": ["Artículo 22 de CFF"],
        "relation_type": NormRelationType.UNKNOWN,
        "source_pages": [1],
        "requires_human_review": True,
    }
    payload.update(overrides)
    return JurisprudenceExtractedMetadata.model_validate(payload)


def test_matching_norm_and_matter_remain_candidate_pending_review() -> None:
    result = assess_session_jurisprudence_applicability(
        hit=_hit(),
        document=_document(),
        metadata=_metadata(),
        applicable_normative_refs={"artículo 22 de cff"},
        matter="administrativa",
    )

    assert result.applicable_candidate is True
    assert result.relevant_to_problem is True
    assert result.relevant_to_norm is True
    assert result.shared_normative_refs == ["Artículo 22 de CFF"]
    assert result.requires_human_review is True


def test_normative_reference_comparison_is_accent_insensitive() -> None:
    result = assess_session_jurisprudence_applicability(
        hit=_hit(),
        document=_document(),
        metadata=_metadata(related_normative_refs=["Artículo 22 de CFF"]),
        applicable_normative_refs={"Articulo 22 de CFF"},
    )

    assert result.relevant_to_norm is True


def test_matter_mismatch_rejects_candidate_for_problem() -> None:
    result = assess_session_jurisprudence_applicability(
        hit=_hit(),
        document=_document(),
        metadata=_metadata(),
        applicable_normative_refs={"Artículo 22 de CFF"},
        matter="Penal",
    )

    assert result.applicable_candidate is False
    assert "matter_mismatch" in result.reasons


def test_unshared_normative_reference_rejects_candidate_for_problem() -> None:
    result = assess_session_jurisprudence_applicability(
        hit=_hit(),
        document=_document(),
        metadata=_metadata(),
        applicable_normative_refs={"Artículo 28 de CFF"},
    )

    assert result.applicable_candidate is False
    assert result.relevant_to_norm is False
    assert "no_shared_normative_ref" in result.reasons


@pytest.mark.parametrize(
    "status",
    [JurisprudenceStatus.SUPERSEDED, JurisprudenceStatus.INVALIDATED],
)
def test_invalid_or_superseded_status_rejects_candidate(
    status: JurisprudenceStatus,
) -> None:
    result = assess_session_jurisprudence_applicability(
        hit=_hit(),
        document=_document(),
        metadata=_metadata(status=status),
        applicable_normative_refs={"Artículo 22 de CFF"},
    )

    assert result.applicable_candidate is False
    assert f"status_{status.value}" in result.reasons


def test_missing_explicit_normative_reference_does_not_invent_relation() -> None:
    result = assess_session_jurisprudence_applicability(
        hit=_hit(),
        document=_document(),
        metadata=_metadata(related_normative_refs=[]),
        applicable_normative_refs={"Artículo 22 de CFF"},
    )

    assert result.applicable_candidate is True
    assert result.relevant_to_norm is False
    assert "no_explicit_normative_ref" in result.reasons
    assert result.requires_human_review is True


def test_conflicting_relation_is_preserved_for_later_conflict_resolution() -> None:
    result = assess_session_jurisprudence_applicability(
        hit=_hit(),
        document=_document(),
        metadata=_metadata(relation_type=NormRelationType.CONFLICTS),
        applicable_normative_refs={"Artículo 22 de CFF"},
    )

    assert result.applicable_candidate is True
    assert result.relation_type is NormRelationType.CONFLICTS
    assert "relation_conflicts" in result.reasons


def test_provenance_mismatch_fails_closed() -> None:
    bad_hit = _hit().model_copy(update={"source_sha256": "d" * 64})

    with pytest.raises(JurisprudenceApplicabilityError, match="huella"):
        assess_session_jurisprudence_applicability(
            hit=bad_hit,
            document=_document(),
            metadata=_metadata(),
            applicable_normative_refs={"Artículo 22 de CFF"},
        )
