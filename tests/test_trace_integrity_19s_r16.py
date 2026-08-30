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

    original_event = payload["result"]["traceability"]["events"][1]
    assert original_event["requires_human_review"] is False

    events = result["result"]["traceability"]["events"]
    assert events[0]["requires_human_review"] is False
    assert events[1]["requires_human_review"] is True
    assert "revisión humana" in events[1]["summary"]


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
