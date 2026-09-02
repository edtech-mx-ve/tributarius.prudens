from pathlib import Path

from app.domain.jurisprudence import (
    JurisprudenceStatus,
    NormRelationType,
)
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_extraction import JurisprudenceExtractedMetadata
from app.domain.jurisprudence_relations import JurisprudenceComparisonType
from app.services.jurisprudence_hybrid_stage import run_session_jurisprudence_stage
from app.services.jurisprudence_metadata_extraction import (
    extract_jurisprudence_metadata,
)
from app.web.runtime_runner import _explanation_mode
from app.web.schemas import WebConsultationRequest
from llm.models import ExplanationMode

SHA = "c" * 64


def _document(text: str) -> JurisprudenceDocumentRepresentation:
    return JurisprudenceDocumentRepresentation(
        document_id="jurisprudencia-integral",
        original_filename="criterio-integral.pdf",
        source_sha256=SHA,
        page_count=1,
        extracted_characters=len(text),
        pages=[
            JurisprudencePage(
                number=1,
                text=text,
                has_extractable_text=True,
            )
        ],
        full_text=text,
    )


def _metadata(
    *,
    relation: NormRelationType = NormRelationType.INTERPRETS,
    normative_ref: str = "CFF:22",
    status: JurisprudenceStatus = JurisprudenceStatus.UNKNOWN,
) -> JurisprudenceExtractedMetadata:
    return JurisprudenceExtractedMetadata(
        identifier="20269999",
        title="DEVOLUCIÓN DE SALDO A FAVOR.",
        court_or_body="Primera Sala",
        status=status,
        matter="fiscal",
        related_normative_refs=[normative_ref],
        relation_type=relation,
        source_pages=[1],
        requires_human_review=True,
    )


def test_integral_metadata_remains_extracted_not_verified() -> None:
    text = """Registro digital: 20269999
Rubro: DEVOLUCIÓN DE SALDO A FAVOR.
Instancia: Primera Sala
Materia: Fiscal
Tipo: Jurisprudencia
Publicación: septiembre de 2026
Se analiza el artículo 22 del CFF.
"""
    result = extract_jurisprudence_metadata(_document(text))

    assert result.identifier == "20269999"
    assert "Artículo 22 de CFF" in result.related_normative_refs
    assert result.requires_human_review is True
    assert result.relation_type is NormRelationType.UNKNOWN


def test_integral_applicable_criterion_is_retrieved_and_classified() -> None:
    document = _document(
        "Devolución de saldo a favor conforme al artículo 22 del CFF."
    )
    result = run_session_jurisprudence_stage(
        query="devolución saldo favor artículo 22",
        documents=[document],
        metadata_by_document_id={
            document.document_id: _metadata(
                relation=NormRelationType.INTERPRETS,
                normative_ref="CFF:22",
            )
        },
        applicable_normative_refs={"CFF:22"},
        matter="fiscal",
        top_k=5,
    )

    assert result.retrieval.returned_count == 1
    assert len(result.applicability) == 1
    assert result.applicability[0].applicable_candidate is True
    assert result.relations.concordant_count == 1
    assert result.relations.assessments[0].relation is (
        JurisprudenceComparisonType.CONCORDANT
    )
    assert result.evidence
    assert result.requires_human_review is True


def test_integral_unrelated_norm_is_distinguished_not_promoted() -> None:
    document = _document(
        "Devolución de saldo a favor conforme al artículo 22 del CFF."
    )
    result = run_session_jurisprudence_stage(
        query="devolución saldo favor artículo 22",
        documents=[document],
        metadata_by_document_id={
            document.document_id: _metadata(
                relation=NormRelationType.INTERPRETS,
                normative_ref="CFF:22",
            )
        },
        applicable_normative_refs={"CFF:28"},
        matter="fiscal",
        top_k=5,
    )

    assert result.applicability[0].applicable_candidate is False
    assert result.relations.distinguishable_count == 1
    assert result.relations.concordant_count == 0
    assert result.evidence == []


def test_integral_explicit_conflict_requires_human_review() -> None:
    document = _document(
        "Devolución de saldo a favor conforme al artículo 22 del CFF."
    )
    result = run_session_jurisprudence_stage(
        query="devolución saldo favor artículo 22",
        documents=[document],
        metadata_by_document_id={
            document.document_id: _metadata(
                relation=NormRelationType.CONFLICTS,
                normative_ref="CFF:22",
            )
        },
        applicable_normative_refs={"CFF:22"},
        matter="fiscal",
        top_k=5,
    )

    assert result.relations.has_conflict is True
    assert result.relations.contradictory_count == 1
    assert result.relations.assessments[0].relation is (
        JurisprudenceComparisonType.CONTRADICTORY
    )
    assert result.requires_human_review is True


def test_integral_student_and_professional_change_only_explanation_mode() -> None:
    student = WebConsultationRequest(
        query="Analiza la devolución del saldo a favor.",
        mode="student",
        jurisprudence_session_id="a" * 32,
    )
    professional = WebConsultationRequest(
        query="Analiza la devolución del saldo a favor.",
        mode="professional",
        jurisprudence_session_id="a" * 32,
    )

    assert _explanation_mode(student.mode) is ExplanationMode.STUDENT
    assert _explanation_mode(professional.mode) is ExplanationMode.PROFESSIONAL
    assert student.query == professional.query
    assert student.jurisprudence_session_id == professional.jurisprudence_session_id


def test_integral_web_contract_sends_session_to_hybrid_orchestration() -> None:
    source = Path("app/web/runtime_runner.py").read_text(encoding="utf-8")

    assert "load_web_jurisprudence_session(" in source
    assert "session_jurisprudence_documents=session_documents" in source
    assert "session_jurisprudence_metadata=session_metadata" in source
    assert "run_hybrid_with_session_jurisprudence(" in source
    assert "explanation_mode=_explanation_mode(request.mode)" in source


def test_integral_traceability_keeps_jurisprudence_and_llm_separate() -> None:
    source = Path("app/services/traceability.py").read_text(encoding="utf-8")

    assert "jurisprudential_sources=_jurisprudence_evidence(result)" in source
    assert "_llm_evidence(result)" in source
    assert 'payload["session_jurisprudence"]' in source
    assert 'payload["llm_trace"]' in source
    assert "SESSION_JURISPRUDENCE_REVIEW" in source


def test_integral_jurisprudence_does_not_override_deterministic_layers() -> None:
    source = Path("app/services/jurisprudence_hybrid_stage.py").read_text(
        encoding="utf-8"
    )

    assert "evaluate_rules" not in source
    assert "run_isr_stage" not in source
    assert "retrieve_similar_cases" not in source
    assert "LlamaRAGService" not in source
