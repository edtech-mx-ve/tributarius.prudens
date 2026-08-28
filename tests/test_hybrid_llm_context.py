from llm.models import DeterministicEvidence, LLMGenerationContext
from llm.prompting import build_messages
from tests.test_hybrid_orchestrator import retrieval


def test_prompt_contains_deterministic_evidence() -> None:
    item = retrieval().hits[0]
    context = LLMGenerationContext(
        question="Calcula ISR",
        evidence=[
            {
                "chunk_id": item.chunk_id,
                "score": item.score,
                "source_type": item.metadata.source_type,
                "source_filename": item.metadata.source_filename,
                "legal_identifier": item.metadata.legal_identifier,
                "page_start": item.metadata.page_start,
                "fiscal_year": item.metadata.fiscal_year,
                "version_label": item.metadata.version_label,
                "text": item.text,
            }
        ],
        deterministic_evidence=DeterministicEvidence(
            applicable_normative_refs=["NORM_TEST_ISR_2026"],
            rule_conclusions=["ISR_RULE_001@1.0: Perfil sujeto a revisión ISR."],
            calculations=["ISR: taxable_base=17000.00; final_tax=2300.00"],
        ),
    )
    messages = build_messages(context)
    assert "final_tax=2300.00" in messages[-1]["content"]
    assert "NORM_TEST_ISR_2026" in messages[-1]["content"]
