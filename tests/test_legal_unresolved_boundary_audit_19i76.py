from __future__ import annotations

from app.services.legal_unresolved_boundary_audit import (
    _shared_prefix_chars,
)


def test_shared_prefix_chars_counts_normalized_prefix() -> None:
    left = "Artículo 31.- Texto jurídico"
    right = "Artículo 31.- Texto jurídico ampliado"
    assert _shared_prefix_chars(left, right) == len(left)


def test_shared_prefix_chars_stops_on_first_difference() -> None:
    left = "Artículo 31.- Alfa"
    right = "Artículo 31.- Beta"
    assert _shared_prefix_chars(left, right) < len(left)
