from app.services import runtime_factory
from app.web import dependencies


def test_dependency_degrades_safely_when_runtime_build_fails(monkeypatch) -> None:
    dependencies.get_web_consultation_service.cache_clear()

    def fail(_settings):
        raise runtime_factory.RuntimeBuildError("fixture")

    monkeypatch.setattr(dependencies, "build_runtime_components", fail)
    service = dependencies.get_web_consultation_service()
    try:
        assert service._runner is None
    finally:
        dependencies.get_web_consultation_service.cache_clear()


def test_dependency_injects_runtime_runner_when_build_succeeds(monkeypatch) -> None:
    dependencies.get_web_consultation_service.cache_clear()
    sentinel = object()

    class Components:
        runner = sentinel

    monkeypatch.setattr(
        dependencies,
        "build_runtime_components",
        lambda _settings: Components(),
    )
    service = dependencies.get_web_consultation_service()
    try:
        assert service._runner is sentinel
    finally:
        dependencies.get_web_consultation_service.cache_clear()
