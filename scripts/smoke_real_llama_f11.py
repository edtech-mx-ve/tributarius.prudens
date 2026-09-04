from __future__ import annotations

import json

from app.core.config import get_settings
from app.services.real_llama_runtime import RealLlamaRuntimeError, build_real_llama_provider
from llm.errors import LLMError


def main() -> int:
    settings = get_settings()
    try:
        provider, descriptor = build_real_llama_provider(settings)
        raw = provider.generate_messages_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Devuelve únicamente JSON válido. No añadas hechos ni fuentes jurídicas."
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "task": "f11_real_llama_smoke",
                            "instruction": "Responde con ok=true y role='controlled_llm'.",
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            response_schema={
                "type": "object",
                "properties": {
                    "ok": {"type": "boolean"},
                    "role": {"type": "string"},
                },
                "required": ["ok", "role"],
                "additionalProperties": False,
            },
        )
        payload = json.loads(raw)
    except (RealLlamaRuntimeError, LLMError, json.JSONDecodeError) as exc:
        print(f"ERROR: smoke Llama real F.11 falló: {exc}")
        return 1

    if payload.get("ok") is not True:
        print("ERROR: Llama real no satisfizo el smoke JSON F.11.")
        return 1
    print("OK: Llama real F.11 respondió mediante llama.cpp")
    print(f"- provider={descriptor.provider_name}")
    print(f"- model={descriptor.model_name}")
    print(f"- sha256={descriptor.model_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
