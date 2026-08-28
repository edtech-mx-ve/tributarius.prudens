from pathlib import Path

import pytest

from llm.errors import LLMConfigurationError
from llm.providers.llama_cpp import LlamaCppProvider


def test_llama_cpp_rejects_missing_model(tmp_path: Path) -> None:
    with pytest.raises(LLMConfigurationError, match="No existe"):
        LlamaCppProvider(tmp_path / "missing.gguf")


def test_llama_cpp_rejects_non_gguf(tmp_path: Path) -> None:
    path = tmp_path / "model.bin"
    path.write_bytes(b"x")

    with pytest.raises(LLMConfigurationError, match="gguf"):
        LlamaCppProvider(path)
