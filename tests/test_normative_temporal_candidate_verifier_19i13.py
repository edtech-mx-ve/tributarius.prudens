from __future__ import annotations

from app.services.normative_temporal_candidate_verifier import classify_scope


def test_scope_detects_amendment_specific_context() -> None:
    scope, _ = classify_scope(
        candidate_line="El presente Decreto entrará en vigor el 1 de enero de 2026.",
        context_before=("Se reforman los artículos 1 y 2 de la Ley.",),
        context_after=("Artículo Segundo Transitorio.",),
    )
    assert scope == "amendment_specific_candidate"


def test_scope_detects_whole_document_candidate_without_reform_signal() -> None:
    scope, _ = classify_scope(
        candidate_line="La presente Ley entrará en vigor el 1 de enero de 2026.",
        context_before=(),
        context_after=(),
    )
    assert scope == "whole_document_candidate"


def test_scope_is_ambiguous_without_scope_signal() -> None:
    scope, _ = classify_scope(
        candidate_line="Entrará en vigor el 1 de enero de 2026.",
        context_before=(),
        context_after=(),
    )
    assert scope == "ambiguous_scope_candidate"
