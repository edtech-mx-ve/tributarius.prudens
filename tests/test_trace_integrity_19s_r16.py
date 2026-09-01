from app.services.trace_integrity_19s_r16 import (
    normative_trace_review_required,
    normative_trace_summary,
    reconcile_traceability_payload,
)


def test_normative_review_propagates_for_fail_closed_abstention() -> None:
    assert normative_trace_review_required(
        global_review_required=True,
        applicable_refs=[],
        has_normative_evidence=True,
    )


def test_normative_review_does_not_propagate_without_normative_evidence() -> None:
    assert not normative_trace_review_required(
        global_review_required=True,
        applicable_refs=[],
        has_normative_evidence=False,
    )


def test_normative_review_does_not_override_successful_applicability() -> None:
    assert not normative_trace_review_required(
        global_review_required=True,
        applicable_refs=["liva:1"],
        has_normative_evidence=True,
    )


def test_normative_summary_explains_abstention() -> None:
    summary = normative_trace_summary(applicable_count=0, review_required=True)
    assert "Referencias normativas aplicables: 0." in summary
    assert "revisión humana" in summary


def test_reconcile_updates_only_normative_trace_and_does_not_mutate_input() -> None:
    payload = {
        "result": {
            "requires_human_review": True,
            "applicable_normative_refs": [],
            "evidence": [
                {"ref_id": "x", "role": "normative", "source_type": "normativa"}
            ],
            "traceability": {
                "events": [
                    {
                        "stage": "retrieval",
                        "requires_human_review": False,
                        "summary": "Chunks recuperados: 5.",
                    },
                    {
                        "stage": "normative",
                        "requires_human_review": False,
                        "summary": "Referencias normativas aplicables: 0.",
                    },
                ]
            },
        }
    }

    result = reconcile_traceability_payload(payload)

    payload_result = payload["result"]
    assert isinstance(payload_result, dict)
    payload_traceability = payload_result["traceability"]
    assert isinstance(payload_traceability, dict)
    payload_events = payload_traceability["events"]
    assert isinstance(payload_events, list)
    original_event = payload_events[1]
    assert isinstance(original_event, dict)
    assert original_event["requires_human_review"] is False

    reconciled_result = result["result"]
    assert isinstance(reconciled_result, dict)
    reconciled_traceability = reconciled_result["traceability"]
    assert isinstance(reconciled_traceability, dict)
    events = reconciled_traceability["events"]
    assert isinstance(events, list)
    first_event = events[0]
    second_event = events[1]
    assert isinstance(first_event, dict)
    assert isinstance(second_event, dict)
    assert first_event["requires_human_review"] is False
    assert second_event["requires_human_review"] is True
    summary = second_event["summary"]
    assert isinstance(summary, str)
    assert "revisión humana" in summary


def test_reconcile_is_noop_when_global_review_is_false() -> None:
    payload = {
        "result": {
            "requires_human_review": False,
            "applicable_normative_refs": [],
            "evidence": [{"role": "normative"}],
            "traceability": {
                "events": [
                    {
                        "stage": "normative",
                        "requires_human_review": False,
                        "summary": "Referencias normativas aplicables: 0.",
                    }
                ]
            },
        }
    }
    assert reconcile_traceability_payload(payload) is payload
