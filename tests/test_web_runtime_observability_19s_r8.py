from __future__ import annotations

import logging

import pytest

from app.services.runtime_factory import RuntimeBuildError
from app.web import dependencies


def test_runtime_build_error_is_logged_without_disabling_safe_degradation(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependencies.get_web_consultation_service.cache_clear()

    monkeypatch.setattr(dependencies, "get_settings", lambda: object())

    def fail_build_runtime(_settings: object) -> None:
        raise RuntimeBuildError("diagnostic-safe-cause")

    monkeypatch.setattr(dependencies, "build_runtime_components", fail_build_runtime)

    with caplog.at_level(logging.WARNING, logger="app.web.dependencies"):
        service = dependencies.get_web_consultation_service()

    assert service is not None
    assert "RuntimeBuildError" in caplog.text
    assert "diagnostic-safe-cause" in caplog.text
    assert "Runtime de consulta no configurado" in caplog.text

    dependencies.get_web_consultation_service.cache_clear()
