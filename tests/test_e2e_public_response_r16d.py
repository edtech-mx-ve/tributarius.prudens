from scripts.e2e_public_response_r16d import (
    Case,
    assert_no_known_mojibake,
    normative_event,
    validate_case,
)


def _payload() -> dict[str, object]:
    return {
        "result": {
            "requires_human_review": True,
            "applicable_normative_refs": [],
            "runtime": {
                "retrieval": "legal_hybrid_lexical_cpu_19s_r14"
            },
            "uncertainties": [],
            "isr": None,
            "isr_result": None,
            "traceability": {
                "primary_intent": "calculate_iva",
                "query_fiscal_year": 2026,
                "events": [
                    {
                        "stage": "normative",
                        "requires_human_review": True,
                        "summary": (
                            "Referencias normativas aplicables: 0. "
                            "Se requiere revisión humana."
                        ),
                    }
                ],
            },
        }
    }


def test_unicode_gate_accepts_clean_payload() -> None:
    assert_no_known_mojibake({"title": "Resolución jurídica"})


def test_unicode_gate_rejects_known_mojibake() -> None:
    try:
        assert_no_known_mojibake({"title": "ResoluciÃ³n"})
    except AssertionError:
        return
    raise AssertionError("debió rechazar mojibake")


def test_normative_event_returns_single_event() -> None:
    result = _payload()["result"]
    assert isinstance(result, dict)
    event = normative_event(result)
    assert event is not None
    assert event["requires_human_review"] is True


def test_iva_case_validates_trace_integrity() -> None:
    case = Case(
        "E2E-04-iva-fail-closed",
        {},
        200,
        "calculate_iva",
        True,
        True,
    )
    validate_case(case, 200, _payload())


def test_failure_messages_are_actionable() -> None:
    case = Case(
        "E2E-X",
        {},
        200,
        expected_intent="calculate_isr",
    )
    payload = _payload()
    try:
        validate_case(case, 200, payload)
    except AssertionError as exc:
        assert "intent" in str(exc)
        return
    raise AssertionError("se esperaba fallo con diagnóstico")
