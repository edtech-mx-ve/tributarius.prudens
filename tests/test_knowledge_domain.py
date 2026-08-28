from datetime import date

import pytest
from pydantic import ValidationError

from app.domain.knowledge import (
    MasterMatrixEntryCreate,
    NormVersionCreate,
    ValidityStatus,
)


def test_norm_version_rejects_inverted_effective_period() -> None:
    with pytest.raises(ValidationError):
        NormVersionCreate(
            legal_unit_id=1,
            version_label="2026",
            effective_from=date(2026, 12, 31),
            effective_to=date(2026, 1, 1),
        )


def test_master_matrix_module_key_is_normalized_contract() -> None:
    entry = MasterMatrixEntryCreate(
        module_key="calcular_isr",
        module_name="Calcular ISR",
        normative_refs=["LISR"],
    )
    assert entry.module_key == "calcular_isr"
    assert entry.normative_refs == ["LISR"]


def test_default_validity_status_is_unknown() -> None:
    item = NormVersionCreate(legal_unit_id=1, version_label="sin_validar")
    assert item.validity_status is ValidityStatus.UNKNOWN
