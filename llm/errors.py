class LLMError(RuntimeError):
    """Error base de integración LLM."""


class LLMConfigurationError(LLMError):
    """Configuración local inválida o backend no disponible."""


class LLMGenerationError(LLMError):
    """Fallo controlado durante la generación."""


class LLMResponseValidationError(LLMError):
    """La salida generada no satisface el contrato estructurado."""
