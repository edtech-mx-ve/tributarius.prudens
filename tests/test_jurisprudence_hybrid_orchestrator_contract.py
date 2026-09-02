from pathlib import Path


def test_hybrid_stage_contract_does_not_override_deterministic_layers() -> None:
    source = Path("app/services/jurisprudence_hybrid_stage.py").read_text(
        encoding="utf-8"
    )

    assert "evaluate_rules" not in source
    assert "run_isr_stage" not in source
    assert "retrieve_similar_cases" not in source
    assert "LlamaRAGService" not in source


def test_hybrid_stage_preserves_explicit_applicable_normative_refs() -> None:
    source = Path("app/services/jurisprudence_hybrid_stage.py").read_text(
        encoding="utf-8"
    )

    assert "applicable_normative_refs=applicable_normative_refs" in source
    assert "analyze_jurisprudence_relations(applicability)" in source
