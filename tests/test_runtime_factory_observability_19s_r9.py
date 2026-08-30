from __future__ import annotations

from app.services.runtime_factory import RuntimeBuildError, _runtime_initialization_error


def test_runtime_initialization_error_preserves_root_type_and_message() -> None:
    root = ValueError("dimension mismatch")
    error = _runtime_initialization_error(root)

    assert isinstance(error, RuntimeBuildError)
    assert "root_type=ValueError" in str(error)
    assert "root_cause=dimension mismatch" in str(error)


def test_runtime_initialization_error_handles_empty_root_message() -> None:
    error = _runtime_initialization_error(ValueError())

    assert "root_type=ValueError" in str(error)
    assert "root_cause=<sin detalle>" in str(error)
