from __future__ import annotations

from app.services.public_safe_runtime_19i18k import _normalize_public_id


def test_prodecon_runtime_alias_normalizes_to_blocked_layer() -> None:
    assert _normalize_public_id("prodecon_contribuyente") == "prodecon"


def test_unam_runtime_alias_normalizes_to_blocked_layer() -> None:
    assert _normalize_public_id("manual_derecho_fiscal_unam") == "manual_unam"


def test_normative_id_is_not_rewritten() -> None:
    assert _normalize_public_id("cff") == "cff"
