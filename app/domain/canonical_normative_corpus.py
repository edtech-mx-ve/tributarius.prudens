from __future__ import annotations

CANONICAL_NORMATIVE_DOCUMENT_IDS = frozenset(
    {
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
)


def is_canonical_normative_document(document_id: str | None) -> bool:
    if document_id is None:
        return False

    normalized = document_id.strip().casefold()
    if not normalized:
        return False

    return normalized in CANONICAL_NORMATIVE_DOCUMENT_IDS
