from __future__ import annotations

from app.domain.jurisprudence import NormRelationType
from app.domain.jurisprudence_decision_application import (
    JurisprudenceCaseApplicationStatus,
    JurisprudenceDecisionEffect,
)
from app.domain.query import ExtractedFact, QueryAnalysis, QueryIntent
from app.services.integral_legal_analyzer import build_integral_legal_analysis
from app.services.jurisprudence_decision_application import (
    evaluate_jurisprudence_for_legal_decision,
)
from app.services.legal_decision import build_legal_decision
from tests.test_block12_4_hypothesis_verification import _orchestrator, _request
from tests.test_block_e5_jurisprudence_evidence_integration import (
    DOC_ID,
    _ratio_record,
    _relation_record,
    _run,
)


def _analysis(
    query: str = "La controversia plantea aplicar el artículo 22 del CFF",
) -> QueryAnalysis:
    return QueryAnalysis(
        original_query=query,
        normalized_query=query,
        primary_intent=QueryIntent.INTERPRET_PROVISION,
        facts=[ExtractedFact(name="controversy", value="controversia planteada")],
    )


def test_e6_applies_mandatory_ratio_when_norm_controversy_and_material_facts_align() -> None:
    session = _run()
    record = evaluate_jurisprudence_for_legal_decision(
        analysis=_analysis(),
        session_result=session,
        ratio_records={DOC_ID: _ratio_record()},
        normative_relation_records={DOC_ID: _relation_record()},
    )

    assert record.applicable_document_ids == [DOC_ID]
    assessment = record.assessments[0]
    assert assessment.status is JurisprudenceCaseApplicationStatus.APPLICABLE
    assert assessment.decision_effect is JurisprudenceDecisionEffect.GOVERNING_INTERPRETATION
    assert assessment.binding_jurisprudence_applies is True
    assert assessment.must_be_respected_by_legal_decision is True
    assert assessment.normative_basis_preserved is True
    assert assessment.can_replace_normative_basis is False
    assert assessment.can_create_second_conclusion is False
    assert assessment.conclusion_consistency_evaluated is False
    assert assessment.requires_human_review is True


def test_e6_does_not_require_identity_of_subject_when_ratio_does_not_depend_on_it() -> None:
    session = _run()
    analysis = _analysis("Persona moral: controversia sobre aplicar el artículo 22 del CFF")
    analysis.facts.append(ExtractedFact(name="taxpayer_type", value="persona moral"))

    record = evaluate_jurisprudence_for_legal_decision(
        analysis=analysis,
        session_result=session,
        ratio_records={DOC_ID: _ratio_record()},
        normative_relation_records={DOC_ID: _relation_record()},
    )

    assert record.assessments[0].status is JurisprudenceCaseApplicationStatus.APPLICABLE
    assert record.assessments[0].hard_material_conflicts == []


def test_e6_requires_review_when_controversy_equivalence_is_not_established() -> None:
    session = _run()
    record = evaluate_jurisprudence_for_legal_decision(
        analysis=_analysis("Consulta completamente distinta sobre sanciones administrativas"),
        session_result=session,
        ratio_records={DOC_ID: _ratio_record()},
        normative_relation_records={DOC_ID: _relation_record()},
    )

    assessment = record.assessments[0]
    assert assessment.status is JurisprudenceCaseApplicationStatus.REVIEW_REQUIRED
    assert assessment.binding_jurisprudence_applies is False
    assert assessment.requires_human_review is True


def test_e6_preserves_explicit_normative_conflict_for_review() -> None:
    session = _run(
        relation_record=_relation_record(relation_type=NormRelationType.CONFLICTS)
    )
    record = evaluate_jurisprudence_for_legal_decision(
        analysis=_analysis(),
        session_result=session,
        ratio_records={DOC_ID: _ratio_record()},
        normative_relation_records={
            DOC_ID: _relation_record(relation_type=NormRelationType.CONFLICTS)
        },
    )

    assessment = record.assessments[0]
    assert assessment.binding_jurisprudence_applies is True
    assert assessment.requires_human_review is True
    assert NormRelationType.CONFLICTS in assessment.relation_types


def test_e6_analyzer_projects_application_without_replacing_canonical_conclusion() -> None:
    base = _orchestrator(None).run(_request())
    session = _run()
    application = evaluate_jurisprudence_for_legal_decision(
        analysis=_analysis(),
        session_result=session,
        ratio_records={DOC_ID: _ratio_record()},
        normative_relation_records={DOC_ID: _relation_record()},
    )
    session = session.model_copy(update={"decision_application": application})
    result = base.model_copy(update={"session_jurisprudence_result": session})

    base_analyzer = build_integral_legal_analysis(base)
    analyzer = build_integral_legal_analysis(result)

    assert analyzer.jurisprudence_application == application
    assert analyzer.canonical_conclusion == base_analyzer.canonical_conclusion
    assert analyzer.controlling_source == base_analyzer.controlling_source


def test_e6_legal_decision_projects_same_application_and_single_conclusion() -> None:
    base = _orchestrator(None).run(_request())
    session = _run()
    application = evaluate_jurisprudence_for_legal_decision(
        analysis=_analysis(),
        session_result=session,
        ratio_records={DOC_ID: _ratio_record()},
        normative_relation_records={DOC_ID: _relation_record()},
    )
    result = base.model_copy(
        update={
            "session_jurisprudence_result": session.model_copy(
                update={"decision_application": application}
            )
        }
    )
    analyzer = build_integral_legal_analysis(result)
    decision = build_legal_decision(analyzer)

    assert decision.jurisprudence_application == analyzer.jurisprudence_application
    assert decision.conclusion == analyzer.canonical_conclusion
    assert decision.controlling_source == analyzer.controlling_source
    assert decision.controlling_source != "jurisprudence"


def test_e6_wrapper_source_executes_application_before_analyzer_projection() -> None:
    source = open("app/services/hybrid_jurisprudence_integration.py", encoding="utf-8").read()
    assert "evaluate_jurisprudence_for_legal_decision(" in source
    assert '"decision_application": decision_application' in source


def test_e6_web_exposes_application_trace_without_recalculation() -> None:
    source = open("app/web/runtime_runner.py", encoding="utf-8").read()
    assert '"e6_application"' in source
    assert "decision_application.model_dump(" in source


def test_e6_reference_thesis_2032043_transfers_ratio_from_justification() -> None:
    from datetime import date

    from app.services.jurisprudence_hybrid_stage import run_session_jurisprudence_stage
    from app.services.jurisprudence_metadata_extraction import (
        extract_jurisprudence_metadata_record,
    )
    from app.services.jurisprudence_normative_relations import (
        build_jurisprudence_normative_relation_record,
    )
    from app.services.jurisprudence_ratio import build_jurisprudence_ratio_record
    from app.services.jurisprudence_temporal_control import (
        build_jurisprudence_temporal_record,
    )
    from tests.test_block_e5_ratio_binding_adjustment import (
        DOC_ID as REF_DOC_ID,
    )
    from tests.test_block_e5_ratio_binding_adjustment import (
        _document as reference_document,
    )

    document = reference_document()
    metadata = extract_jurisprudence_metadata_record(document)
    relations = build_jurisprudence_normative_relation_record(
        document,
        metadata_record=metadata,
    )
    temporal = build_jurisprudence_temporal_record(metadata)
    ratio = build_jurisprudence_ratio_record(metadata)
    session = run_session_jurisprudence_stage(
        query="RESICO subordinación jerárquica límite ingresos artículo 113-E",
        documents=[document],
        metadata_by_document_id={REF_DOC_ID: metadata.extracted},
        applicable_normative_refs={"lisr:articulo_113_e"},
        matter="fiscal",
        top_k=5,
        normative_relation_records={REF_DOC_ID: relations},
        temporal_records={REF_DOC_ID: temporal},
        ratio_records={REF_DOC_ID: ratio},
        query_date=date(2026, 9, 3),
    )
    query_analysis = QueryAnalysis(
        original_query="RESICO: límite de ingresos y subordinación jerárquica",
        normalized_query="RESICO límite ingresos subordinación jerárquica",
        primary_intent=QueryIntent.INTERPRET_PROVISION,
        facts=[
            ExtractedFact(name="fiscal_regime", value="RESICO"),
            ExtractedFact(name="issue", value="límite de ingresos"),
        ],
    )

    application = evaluate_jurisprudence_for_legal_decision(
        analysis=query_analysis,
        session_result=session,
        ratio_records={REF_DOC_ID: ratio},
        normative_relation_records={REF_DOC_ID: relations},
    )

    assessment = application.assessments[0]
    assert assessment.status is JurisprudenceCaseApplicationStatus.APPLICABLE
    assert assessment.binding_jurisprudence_applies is True
    assert assessment.shared_normative_refs == ["lisr:articulo_113_e"]
    assert assessment.ratio_transfer_established is True
    assert "resico" in " ".join(assessment.matched_controversy_terms)
