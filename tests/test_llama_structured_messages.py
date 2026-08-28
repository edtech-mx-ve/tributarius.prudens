from pathlib import Path

import pytest

from llm.errors import LLMConfigurationError
from llm.providers.llama_cpp import LlamaCppProvider


def test_llama_provider_still_validates_model_path(tmp_path: Path) -> None:
    with pytest.raises(LLMConfigurationError):
        LlamaCppProvider(tmp_path / "missing.gguf")
