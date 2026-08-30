from __future__ import annotations

import argparse
import json
import urllib.request
from typing import Any, cast


def _post(base_url: str, timeout: float) -> dict[str, Any]:
    payload = {
        "query": (
            "Para el ejercicio fiscal 2026, ¿qué tasa de IVA debo aplicar "
            "a una operación gravada en México?"
        ),
        "mode": "taxpayer",
        "fiscal_year": 2026,
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/v1/consultations",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        decoded: Any = json.loads(response.read().decode("utf-8"))

    if not isinstance(decoded, dict):
        raise ValueError("La respuesta pública JSON debe ser un objeto.")
    return cast(dict[str, Any], decoded)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Smoke r16F del contrato de integridad de explicación."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()

    payload = _post(args.base_url, args.timeout)
    result = payload.get("result")
    if not isinstance(result, dict):
        print("FAIL: result ausente o inválido.")
        return 1

    integrity = result.get("explanation_integrity")
    if not isinstance(integrity, dict):
        print("FAIL: explanation_integrity ausente.")
        return 1

    status = integrity.get("status")
    policy = integrity.get("policy")
    llm_authority = integrity.get("llm_authority")
    review = integrity.get("requires_human_review")
    applicable = integrity.get("applicable_normative_ref_count")
    evidence = integrity.get("evidence_count")

    print(f"status={status}")
    print(f"policy={policy}")
    print(f"llm_authority={llm_authority}")
    print(f"requires_human_review={review}")
    print(f"applicable_normative_ref_count={applicable}")
    print(f"evidence_count={evidence}")

    if policy != "evidence_bound_fail_closed":
        print("FAIL: política de integridad inesperada.")
        return 1
    if llm_authority != "none":
        print("FAIL: un LLM no debe tener autoridad normativa en r16F.")
        return 1
    if status in {"grounded_applicable_norm"} and review is True:
        print("FAIL: estado grounded incompatible con revisión humana.")
        return 1

    print("PASS: r16F contrato de integridad de explicación activo.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
