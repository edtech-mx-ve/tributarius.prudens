from __future__ import annotations

import pytest

from app.domain.legal_hypothesis import (
    ControlledLegalHypothesis,
    LegalHypothesisStatus,
)
from app.services.legal_hypothesis_control import (
    LegalHypothesisValidationError,
    validate_controlled_legal_hypothesis,
)


def _hypothesis(**overrides: object) -> ControlledLegalHypothesis:
    payload: dict[str, object] = {
        "issue": "Determinar si existe una obligación fiscal aplicable.",
        "hypothesis": (
            "Podría existir una obligación fiscal que debe verificarse "
            "contra la normativa recuperada."
        ),
        "investigation_targets": [
            "Verificar sujeto, hecho imponible, temporalidad y fundamento."
        ],
        "evidence_ids": ["chunk-legal-001"],
        "uncertainties": [],
    }
    payload.update(overrides)
    return ControlledLegalHypothesis.model_validate(payload)


def test_controlled_hypothesis_is_only_proposed_and_requires_validation() -> None:
    result = validate_controlled_legal_hypothesis(
        _hypothesis(),
        authorized_evidence_ids=["chunk-legal-001"],
    )

    assert result.generation_performed is True
    assert result.hypothesis is not None
    assert result.hypothesis.status == LegalHypothesisStatus.PROPOSED
    assert result.hypothesis.requires_validation is True
    assert "legal_hypothesis:deterministic_result_unchanged=true" in result.trace


def test_hypothesis_cannot_cite_unauthorized_evidence() -> None:
    with pytest.raises(
        LegalHypothesisValidationError,
        match="fuera del contexto autorizado",
    ):
        validate_controlled_legal_hypothesis(
            _hypothesis(evidence_ids=["chunk-invented-999"]),
            authorized_evidence_ids=["chunk-legal-001"],
        )


def test_hypothesis_cannot_change_deterministic_result() -> None:
    with pytest.raises(
        LegalHypothesisValidationError,
        match="no puede modificar resultados jurídicos deterministas",
    ):
        validate_controlled_legal_hypothesis(
            _hypothesis(changes_deterministic_result=True),
            authorized_evidence_ids=["chunk-legal-001"],
        )


def test_hypothesis_cannot_assert_external_legal_authority() -> None:
    with pytest.raises(
        LegalHypothesisValidationError,
        match="no puede introducir autoridad jurídica externa",
    ):
        validate_controlled_legal_hypothesis(
            _hypothesis(asserts_external_legal_authority=True),
            authorized_evidence_ids=["chunk-legal-001"],
        )


def test_hypothesis_cannot_disable_later_validation() -> None:
    with pytest.raises(
        LegalHypothesisValidationError,
        match="debe quedar sujeta a validación",
    ):
        validate_controlled_legal_hypothesis(
            _hypothesis(requires_validation=False),
            authorized_evidence_ids=["chunk-legal-001"],
        )


def test_uncertainty_escalates_review_without_becoming_conclusion() -> None:
    result = validate_controlled_legal_hypothesis(
        _hypothesis(uncertainties=["Falta precisar el ejercicio fiscal."]),
        authorized_evidence_ids=["chunk-legal-001"],
    )

    assert result.requires_human_review is True
    assert result.hypothesis is not None
    assert result.hypothesis.status == LegalHypothesisStatus.PROPOSED
    assert result.hypothesis.changes_deterministic_result is False
