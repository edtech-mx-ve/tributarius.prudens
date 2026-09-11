import json

from llm.models import DeterministicEvidence, LLMGenerationContext
from llm.prompting import build_messages
from llm.rag_compact_contracts import rag_compact_response_schema
from llm.rag_compact_prompting import build_compact_rag_messages
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


def test_compact_prompt_exposes_deterministic_isr_calculation() -> None:
    item = retrieval().hits[0]
    calculation = "ISR: taxable_base=35000.00; final_tax=499.50"
    context = LLMGenerationContext(
        question="Calcula ISR provisional",
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
            calculations=[calculation],
        ),
    )

    messages = build_compact_rag_messages(context)
    payload = json.loads(messages[-1]["content"])

    assert payload["deterministic_summary"]["calculations"] == [calculation]
    assert payload["selection_catalog"]["calculation_refs"] == [calculation]

    schema = rag_compact_response_schema(context)
    calculation_schema = schema["properties"]["calculation_ref_indices"]

    assert "calculation_ref_indices" in schema["required"]
    assert calculation_schema["minItems"] == 1
    assert calculation_schema["maxItems"] == 1
    assert calculation_schema["uniqueItems"] is True
    assert calculation_schema["items"]["enum"] == [0]
