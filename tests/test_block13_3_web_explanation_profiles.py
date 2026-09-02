from __future__ import annotations

from typing import cast

from app.domain.explanation_mode import ExplanationMode
from app.services.legal_explanation_profile import (
    get_legal_explanation_profile,
)
from app.web.presenter import _present_explanation_profile
from app.web.schemas import WebConsultationRequest


def _string_list(value: object) -> list[str]:
    assert isinstance(value, list)
    return cast(list[str], value)


def test_web_profile_maps_all_three_public_modes() -> None:
    taxpayer = _present_explanation_profile("taxpayer")
    student = _present_explanation_profile("student")
    professional = _present_explanation_profile("professional")

    assert taxpayer["audience_label"] == "Contribuyente"
    assert student["audience_label"] == "Estudiante"
    assert professional["audience_label"] == "Profesional"

    assert taxpayer["mode"] == "taxpayer"
    assert student["mode"] == "student"
    assert professional["mode"] == "professional"


def test_web_profiles_differ_only_in_communication_metadata() -> None:
    profiles = [
        _present_explanation_profile(mode.value)
        for mode in ExplanationMode
    ]

    assert len({tuple(_string_list(item["sections"])) for item in profiles}) == 3
    assert (
        len(
            {
                tuple(_string_list(item["style_instructions"]))
                for item in profiles
            }
        )
        == 3
    )
    assert len({item["communication_goal"] for item in profiles}) == 3


def test_web_profile_does_not_expose_or_recompute_legal_result_fields() -> None:
    forbidden = {
        "hybrid_conclusion",
        "hybrid_controlling_source",
        "applicable_normative_refs",
        "rule_conclusions",
        "calculations",
        "similar_cases",
        "jurisprudential_criteria",
        "requires_human_review",
        "heuristic_signals",
        "heuristic_priorities",
    }

    for mode in ExplanationMode:
        profile = _present_explanation_profile(mode.value)
        assert forbidden.isdisjoint(profile)


def test_profile_accessor_returns_defensive_copy() -> None:
    first = get_legal_explanation_profile(ExplanationMode.TAXPAYER)
    first.section_order.append("mutacion_indebida")

    second = get_legal_explanation_profile(ExplanationMode.TAXPAYER)

    assert "mutacion_indebida" not in second.section_order


def test_web_request_accepts_exactly_the_three_explanation_modes() -> None:
    for mode in ExplanationMode:
        request = WebConsultationRequest(
            query="¿Qué obligación fiscal existe?",
            mode=mode.value,
        )
        assert request.mode == mode.value


def test_public_profile_contract_preserves_historical_labels() -> None:
    assert get_legal_explanation_profile(
        ExplanationMode.TAXPAYER
    ).audience_label == "Contribuyente"
    assert get_legal_explanation_profile(
        ExplanationMode.STUDENT
    ).audience_label == "Estudiante"
    assert get_legal_explanation_profile(
        ExplanationMode.PROFESSIONAL
    ).audience_label == "Profesional"
