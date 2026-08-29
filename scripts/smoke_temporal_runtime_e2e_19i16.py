from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from fastapi.testclient import TestClient

from app.main import app


class SmokeFailure(RuntimeError):
    """Fallo controlado del smoke E2E temporal."""


def _as_dict(value: object, *, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise SmokeFailure(f"{label} no es un objeto JSON.")
    return value


def _as_list(value: object, *, label: str) -> list[object]:
    if not isinstance(value, list):
        raise SmokeFailure(f"{label} no es una lista JSON.")
    return value


def _document_ids(payload: dict[str, Any]) -> set[str]:
    evidence = _as_list(payload.get("evidence"), label="evidence")
    document_ids: set[str] = set()
    for raw_item in evidence:
        item = _as_dict(raw_item, label="evidence item")
        document_id = item.get("document_id")
        if isinstance(document_id, str) and document_id.strip():
            document_ids.add(document_id.strip().casefold())
    return document_ids


def _normative_refs(payload: dict[str, Any]) -> list[object]:
    raw = payload.get("applicable_normative_refs", [])
    return _as_list(raw, label="applicable_normative_refs")


def _evidence_document_by_ref(payload: dict[str, Any]) -> dict[str, str]:
    evidence = _as_list(payload.get("evidence"), label="evidence")
    mapping: dict[str, str] = {}
    for raw_item in evidence:
        item = _as_dict(raw_item, label="evidence item")
        ref_id = item.get("ref_id")
        document_id = item.get("document_id")
        if (
            isinstance(ref_id, str)
            and ref_id.strip()
            and isinstance(document_id, str)
            and document_id.strip()
        ):
            mapping[ref_id.strip()] = document_id.strip().casefold()
    return mapping


def _blocked_promotions(
    payload: dict[str, Any],
    *,
    blocked_documents: set[str],
) -> list[tuple[str, str]]:
    ref_to_document = _evidence_document_by_ref(payload)
    blocked: list[tuple[str, str]] = []
    for raw_ref in _normative_refs(payload):
        if not isinstance(raw_ref, str):
            raise SmokeFailure("applicable_normative_refs contiene un valor no textual.")
        document_id = ref_to_document.get(raw_ref)
        if document_id in blocked_documents:
            blocked.append((raw_ref, document_id))
    return blocked


def _post_consultation(client: TestClient, query: str) -> dict[str, Any]:
    response = client.post(
        "/api/v1/consultations",
        json={
            "query": query,
            "mode": "professional",
            "fiscal_year": 2026,
        },
    )
    if response.status_code != 200:
        raise SmokeFailure(
            f"Consulta HTTP {response.status_code}: {response.text[:500]}"
        )

    envelope = _as_dict(response.json(), label="consultation response")
    status = envelope.get("status")
    if status != "ready":
        raise SmokeFailure(
            "Consulta no disponible: "
            f"status={status!r}; message={envelope.get('message')!r}"
        )
    result = envelope.get("result")
    return _as_dict(result, label="consultation result")


def _assert_contains(
    values: Iterable[str],
    expected: str,
    *,
    label: str,
) -> None:
    normalized = {value.casefold() for value in values}
    if expected.casefold() not in normalized:
        raise SmokeFailure(f"{label}: falta {expected!r}; obtenido={sorted(normalized)}")


def main() -> int:
    try:
        with TestClient(app) as client:
            ready = client.get("/ready")
            health = client.get("/health")
            root = client.get("/")
            if ready.status_code != 200:
                raise SmokeFailure(f"/ready={ready.status_code}: {ready.text[:500]}")
            if health.status_code != 200:
                raise SmokeFailure(f"/health={health.status_code}")
            if root.status_code != 200:
                raise SmokeFailure(f"/={root.status_code}")

            cases = (
                (
                    "LIVA",
                    "¿Qué establece la Ley del IVA sobre los actos o actividades gravados?",
                    "liva",
                    True,
                ),
                (
                    "CPEUM",
                    "¿Qué establece el artículo 31 fracción IV de la "
                    "Constitución sobre contribuir al gasto público?",
                    "cpeum",
                    True,
                ),
                (
                    "LIEPS",
                    "¿Qué obligaciones fiscales contempla la Ley del IEPS?",
                    "lieps",
                    False,
                ),
            )

            print("OK: endpoints base disponibles")
            print(f"- /ready={ready.status_code}")
            print(f"- /health={health.status_code}")
            print(f"- /={root.status_code}")

            for label, query, expected_document, must_be_temporally_blocked in cases:
                payload = _post_consultation(client, query)
                docs = _document_ids(payload)
                refs = _normative_refs(payload)
                _assert_contains(
                    docs,
                    expected_document,
                    label=f"{label} evidencia RAG",
                )
                blocked_promotions = _blocked_promotions(
                    payload,
                    blocked_documents={"liva", "cpeum"},
                )
                if must_be_temporally_blocked and blocked_promotions:
                    raise SmokeFailure(
                        f"{label}: el guard permitió promoción de documento bloqueado; "
                        f"obtenido={json.dumps(blocked_promotions, ensure_ascii=False)}"
                    )

                print(
                    f"- {label}: evidence_document_found=True; "
                    f"normative_refs={len(refs)}; "
                    f"blocked_promotions={len(blocked_promotions)}; "
                    f"temporal_guard_expected={must_be_temporally_blocked}"
                )

            print(
                "OK: Sprint 19I.16; evidencia RAG preservada y guard temporal "
                "aplicado E2E"
            )
            print(
                "POLICY: LIVA/CPEUM pueden recuperarse como evidencia; sus propias "
                "referencias no pueden promoverse mientras su vigencia documental "
                "sea unknown_fail_closed. Otras normas aplicables pueden coexistir."
            )
    except SmokeFailure as exc:
        print(f"ERROR: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
