from app.domain.canonical_normative_corpus import (
    CANONICAL_NORMATIVE_DOCUMENT_IDS,
    is_canonical_normative_document,
)

EXPECTED = {
    "cff",
    "cpeum",
    "lfdc",
    "lfisan",
    "lfpca",
    "lieps",
    "lif_2026",
    "lisr",
    "liva",
    "lotfja",
    "reg_cff",
    "reg_lisr_060516",
    "reg_liva_250914",
    "rmf_2026",
}


def test_canonical_normative_inventory_is_exact() -> None:
    assert CANONICAL_NORMATIVE_DOCUMENT_IDS == EXPECTED
    assert len(CANONICAL_NORMATIVE_DOCUMENT_IDS) == 14


def test_canonical_lookup_normalizes_document_id() -> None:
    assert is_canonical_normative_document(" CFF ") is True
    assert is_canonical_normative_document("RMF_2026") is True


def test_unknown_normative_document_is_not_canonical() -> None:
    assert is_canonical_normative_document("external") is False
    assert is_canonical_normative_document(None) is False
