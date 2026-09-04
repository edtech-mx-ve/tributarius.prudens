from __future__ import annotations

from datetime import date

from app.domain.jurisprudence import JurisprudenceCriterionType, NormRelationType
from app.domain.jurisprudence_document import (
    JurisprudenceDocumentRepresentation,
    JurisprudencePage,
)
from app.domain.jurisprudence_evidence import JurisprudenceEvidenceDecision
from app.domain.jurisprudence_ratio import JurisprudenceRatioSourceSection
from app.domain.jurisprudence_temporal import JurisprudenceBindingTemporalState
from app.services.jurisprudence_hybrid_stage import run_session_jurisprudence_stage
from app.services.jurisprudence_metadata_extraction import (
    extract_jurisprudence_metadata_record,
)
from app.services.jurisprudence_normative_relations import (
    build_jurisprudence_normative_relation_record,
)
from app.services.jurisprudence_ratio import build_jurisprudence_ratio_record
from app.services.jurisprudence_temporal_control import (
    assess_jurisprudence_temporal_context,
    build_jurisprudence_temporal_record,
)

SHA = "f" * 64
DOC_ID = "tesis-2032043-e5"

SOURCE_TEXT = """Registro digital: 2032043
RÉGIMEN SIMPLIFICADO DE CONFIANZA PARA PERSONAS FÍSICAS EN EL IMPUESTO
SOBRE LA RENTA (RESICO). LA REGLA 3.13.33. DE LA RESOLUCIÓN MISCELÁNEA FISCAL
PARA 2023 NO VIOLA EL PRINCIPIO DE SUBORDINACIÓN JERÁRQUICA.
Hechos: Una persona física impugnó la regla 3.13.33. de la RMF 2023 porque estimó
que contravenía el artículo 113-E de la Ley del Impuesto sobre la Renta.
Criterio jurídico: La regla 3.13.33. de la Resolución Miscelánea Fiscal para 2023
no viola el principio de subordinación jerárquica.
Justificación: Conforme al artículo 113-E de la Ley del Impuesto sobre la Renta,
el límite de ingresos es una condición sustantiva del RESICO. Una vez superado el
límite económico, su artículo 113-E debe leerse en el sentido de que la persona ya
no reúne la característica económica del RESICO para ese ejercicio fiscal.
Instancia: Pleno
Materia(s): Constitucional
Tesis: P./J. 58/2026 (12a.)
Fuente: Semanario Judicial de la Federación.
Tipo: Jurisprudencia
Publicación: viernes 17 de abril de 2026 10:21 h
Esta tesis se publicó el viernes 17 de abril de 2026 a las 10:21 horas en el
Semanario Judicial de la Federación y, por ende, se considera de aplicación
obligatoria a partir del lunes 20 de abril de 2026.
"""


def _document() -> JurisprudenceDocumentRepresentation:
    return JurisprudenceDocumentRepresentation(
        document_id=DOC_ID,
        original_filename="Tesis2032043.pdf",
        source_sha256=SHA,
        page_count=1,
        extracted_characters=len(SOURCE_TEXT),
        pages=[
            JurisprudencePage(
                number=1,
                text=SOURCE_TEXT,
                has_extractable_text=True,
            )
        ],
        full_text=SOURCE_TEXT,
    )


def test_adjustment_extracts_official_sections_and_ratio_source() -> None:
    metadata = extract_jurisprudence_metadata_record(_document())
    ratio = build_jurisprudence_ratio_record(metadata)

    assert metadata.extracted.criterion_type is JurisprudenceCriterionType.JURISPRUDENCE
    assert metadata.extracted.facts_text is not None
    assert metadata.extracted.legal_criterion_text is not None
    assert metadata.extracted.justification_text is not None
    assert "113-E" in metadata.extracted.justification_text
    assert metadata.extracted.binding_effective_date_text == "lunes 20 de abril de 2026"
    assert ratio.ratio_source_section is JurisprudenceRatioSourceSection.JUSTIFICATION
    assert ratio.ratio_source_text == metadata.extracted.justification_text
    assert ratio.structured_thesis_sections_established is True
    assert ratio.ratio_material_delimitation_completed is False


def test_adjustment_type_jurisprudence_sets_binding_character_and_effective_date() -> None:
    metadata = extract_jurisprudence_metadata_record(_document())
    temporal = build_jurisprudence_temporal_record(metadata)

    assert temporal.binding_character_mandatory is True
    assert temporal.binding_force_evaluated is True
    assert temporal.parsed_publication_start == date(2026, 4, 17)
    assert temporal.parsed_binding_start == date(2026, 4, 20)

    before = assess_jurisprudence_temporal_context(
        temporal,
        query_date=date(2026, 4, 19),
    )
    effective = assess_jurisprudence_temporal_context(
        temporal,
        query_date=date(2026, 4, 20),
    )

    assert before.mandatory_by_query_date is False
    assert before.temporally_eligible_for_evidence is False
    assert effective.binding_state is JurisprudenceBindingTemporalState.MANDATORY_BY_QUERY_DATE
    assert effective.mandatory_by_query_date is True
    assert effective.temporally_eligible_for_evidence is True


def test_adjustment_e3_detects_interpretive_relation_inside_justification() -> None:
    metadata = extract_jurisprudence_metadata_record(_document())
    relations = build_jurisprudence_normative_relation_record(
        _document(),
        metadata_record=metadata,
    )

    match = next(
        mention
        for mention in relations.mentions
        if mention.candidate_normative_ref == "lisr:articulo_113_e"
        and mention.material_relation_explicit
    )
    assert match.relation_type is NormRelationType.INTERPRETS


def test_adjustment_e5_admits_only_after_binding_and_with_justification_ratio() -> None:
    document = _document()
    metadata = extract_jurisprudence_metadata_record(document)
    relations = build_jurisprudence_normative_relation_record(
        document,
        metadata_record=metadata,
    )
    temporal = build_jurisprudence_temporal_record(metadata)
    ratio = build_jurisprudence_ratio_record(metadata)

    result = run_session_jurisprudence_stage(
        query="RESICO interpretación artículo 113-E límite de ingresos",
        documents=[document],
        metadata_by_document_id={DOC_ID: metadata.extracted},
        applicable_normative_refs={"lisr:articulo_113_e"},
        matter="fiscal",
        top_k=5,
        normative_relation_records={DOC_ID: relations},
        temporal_records={DOC_ID: temporal},
        ratio_records={DOC_ID: ratio},
        query_date=date(2026, 4, 20),
    )

    integration = result.evidence_integration
    assert integration is not None
    assert integration.admitted_count == 1
    assessment = integration.assessments[0]
    assert assessment.decision is JurisprudenceEvidenceDecision.ADMITTED
    assert assessment.binding_character_mandatory is True
    assert assessment.mandatory_by_query_date is True
    assert assessment.ratio_source_established is True
    assert assessment.justification_normative_relevance_established is True
    assert assessment.legal_applicability_determined is False
    assert assessment.can_control_legal_decision is False
