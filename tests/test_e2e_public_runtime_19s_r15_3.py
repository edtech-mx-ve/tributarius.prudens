from pathlib import Path

from scripts.e2e_public_runtime_19s_r15_3 import EXPECTED_FILES, EXPECTED_SHA256


def test_r15_3_pins_repaired_r10_candidate() -> None:
    assert EXPECTED_SHA256 == "18ac85d3b2612a3057dd6e24660487457af078eb8abdf2bb94e122c9bc97c514"


def test_r15_3_uses_exact_public_candidate_contract() -> None:
    assert EXPECTED_FILES == {
        "runtime/index.faiss",
        "runtime/chunks.jsonl",
        "runtime/manifest.json",
        "release_metadata.json",
        "release_manifest.json",
    }


def test_r15_3_does_not_reference_private_semantic_runtime() -> None:
    source = Path("scripts/e2e_public_runtime_19s_r15_3.py").read_text(encoding="utf-8")
    assert "runtime_artifacts_semantic_v2" not in source
    assert 'RAG_RUNTIME_BACKEND"] = "lexical_cpu"' in source
