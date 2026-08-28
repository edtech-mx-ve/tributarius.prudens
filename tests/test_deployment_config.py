from pathlib import Path

from app.core.config import Settings
from scripts.validate_deployment import validate_render_blueprint


def test_render_blueprint_is_free_and_stateless() -> None:
    checks = validate_render_blueprint(Path("render.yaml"))
    assert "plan=free" in checks
    assert "sqlite-is-ephemeral" in checks
    assert "no-databases" in checks
    assert "no-disk" in checks


def test_render_settings_contract() -> None:
    settings = Settings(
        _env_file=None,
        environment="production",
        deployment_platform="render",
        runtime_profile="stateless_free",
        database_url="sqlite:////tmp/tributarius-prudens.db",
        trusted_hosts_csv="*.onrender.com",
        rag_artifact_dir="deployment/runtime_artifacts",
        require_rag_artifacts=False,
    )
    assert settings.deployment_platform == "render"
    assert settings.runtime_profile == "stateless_free"
    assert settings.trusted_hosts() == ["*.onrender.com"]
