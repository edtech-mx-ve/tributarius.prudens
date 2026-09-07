from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.services.hybrid_legal_decision import build_hybrid_legal_decision
from tests.test_block_f9_hybrid_legal_decision import _verified_analysis
from tests.test_block_g1_legal_consultation_report import (
    _components,
    _report,
)


def test_g8_accepts_consistent_analyzer_1_0_and_legal_decision_1_0() -> None:
    report = _report()

    assert report.analyzer.schema_version == "1.0"
    assert report.legal_decision.schema_version == "1.0"
    assert (
        report.legal_decision.conclusion
        == report.analyzer.canonical_conclusion
    )
    assert (
        report.legal_decision.controlling_source
        == report.analyzer.controlling_source
    )


def test_g8_accepts_consistent_hybrid_f8_f9_pair() -> None:
    analysis = _verified_analysis()
    decision = build_hybrid_legal_decision(analysis)

    report = _report(
        analyzer=analysis,
        legal_decision=decision,
    )

    assert report.analyzer.schema_version == "1.1"
    assert report.legal_decision.schema_version == "1.1"

    analyzer_projection = report.analyzer.hybrid_projection
    decision_projection = report.legal_decision.hybrid_projection

    assert (
        analyzer_projection.verification_packet_sha256
        == decision_projection.source_verification_packet_sha256
    )
    assert (
        report.analyzer.canonical_conclusion
        == decision_projection.source_canonical_conclusion
    )
    assert analyzer_projection.reasoning_controller == "rbs"
    assert (
        analyzer_projection.legal_authority_source
        == "normative_evidence"
    )
    assert decision_projection.single_determination_preserved is True
    assert decision_projection.second_conclusion_created is False


def test_g8_rejects_hybrid_analyzer_with_legacy_decision() -> None:
    _, _, legacy_decision = _components()
    hybrid_analysis = _verified_analysis()

    with pytest.raises(
        ValidationError,
        match="misma familia hibrida",
    ):
        _report(
            analyzer=hybrid_analysis,
            legal_decision=legacy_decision,
        )


def test_g8_rejects_legacy_analyzer_with_hybrid_decision() -> None:
    _, legacy_analysis, _ = _components()
    hybrid_analysis = _verified_analysis()
    hybrid_decision = build_hybrid_legal_decision(hybrid_analysis)

    with pytest.raises(
        ValidationError,
        match="misma familia hibrida",
    ):
        _report(
            analyzer=legacy_analysis,
            legal_decision=hybrid_decision,
        )


def test_g8_rejects_divergent_f7_verification_packet() -> None:
    analysis = _verified_analysis()
    decision = build_hybrid_legal_decision(analysis)

    altered_projection = decision.hybrid_projection.model_copy(
        update={
            "source_verification_packet_sha256": "0" * 64,
        }
    )
    altered_decision = decision.model_copy(
        update={"hybrid_projection": altered_projection}
    )

    with pytest.raises(
        ValidationError,
        match="paquetes F.7 distintos",
    ):
        _report(
            analyzer=analysis,
            legal_decision=altered_decision,
        )


def test_g8_rejects_changed_legacy_controlling_source() -> None:
    _, analysis, decision = _components()

    altered_decision = decision.model_copy(
        update={"controlling_source": "cbr"}
    )

    with pytest.raises(
        ValidationError,
        match="fuente controladora",
    ):
        _report(
            analyzer=analysis,
            legal_decision=altered_decision,
        )
