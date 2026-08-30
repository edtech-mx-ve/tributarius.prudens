from app.services.public_response_quality_19s_r16 import (
    dedupe_evidence,
    normalize_public_value,
    normative_review_reason,
    repair_mojibake,
)


def test_repair_mojibake_repairs_known_lossy_damage() -> None:
    assert repair_mojibake("PolÃtica jurÃdica") == "Política jurídica"
    assert repair_mojibake("ArtÃculo") == "Artículo"
    assert repair_mojibake("Ãndice RAG") == "Índice RAG"


def test_repair_mojibake_repairs_reversible_cp1252_damage() -> None:
    assert repair_mojibake("regla â€” evidencia") == "regla — evidencia"
    assert repair_mojibake("cÃ¡lculo") == "cálculo"


def test_repair_mojibake_preserves_valid_unicode() -> None:
    value = "Política jurídica: México — IVA"
    assert repair_mojibake(value) == value


def test_unknown_lossy_sequence_is_not_guessed() -> None:
    assert repair_mojibake("dato Ãx") == "dato Ãx"


def test_normalize_public_value_is_recursive_and_non_mutating() -> None:
    source = {"capabilities": [{"detail": "Ãndice RAG presente."}]}
    result = normalize_public_value(source)
    assert result["capabilities"][0]["detail"] == "Índice RAG presente."
    assert source["capabilities"][0]["detail"] == "Ãndice RAG presente."


def test_dedupe_evidence_preserves_first_reference() -> None:
    evidence = [
        {"ref_id": "a", "kind": "document", "score": 0.9},
        {"ref_id": "a", "kind": "normative", "score": 0.8},
        {"ref_id": "b", "kind": "document", "score": 0.7},
    ]
    result = dedupe_evidence(evidence)
    assert [item["ref_id"] for item in result] == ["a", "b"]
    assert result[0]["kind"] == "document"


def test_normative_review_reason_is_fail_closed() -> None:
    reason = normative_review_reason(
        has_material_evidence=True,
        applicable_refs=[],
        temporal_or_normative_review=False,
    )
    assert reason is not None
    assert "ninguna referencia" in reason


def test_normative_review_reason_absent_when_gate_is_satisfied() -> None:
    assert (
        normative_review_reason(
            has_material_evidence=True,
            applicable_refs=["liva:1"],
            temporal_or_normative_review=False,
        )
        is None
    )
