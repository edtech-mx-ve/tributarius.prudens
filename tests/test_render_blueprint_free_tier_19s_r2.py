from pathlib import Path

import yaml

PUBLIC_RUNTIME_SHA256 = (
    "18ac85d3b2612a3057dd6e24660487457af078eb8abdf2bb94e122c9bc97c514"
)


def _service() -> dict[str, object]:
    data = yaml.safe_load(Path("render.yaml").read_text(encoding="utf-8"))
    services = data["services"]
    assert isinstance(services, list)
    assert len(services) == 1
    service = services[0]
    assert isinstance(service, dict)
    return service


def test_render_free_tier_does_not_define_shutdown_delay() -> None:
    service = _service()
    assert service["plan"] == "free"
    assert "maxShutdownDelaySeconds" not in service


def test_render_build_runs_verified_runtime_bootstrap() -> None:
    service = _service()
    build_command = str(service["buildCommand"])
    assert "python -m scripts.bootstrap_runtime_release_19i18c" in build_command


def test_render_pins_public_runtime_sha_and_external_url() -> None:
    service = _service()
    env_vars = service["envVars"]
    assert isinstance(env_vars, list)

    by_key = {
        str(item["key"]): item
        for item in env_vars
        if isinstance(item, dict) and "key" in item
    }

    assert by_key["RUNTIME_RELEASE_SHA256"]["value"] == PUBLIC_RUNTIME_SHA256
    assert by_key["RUNTIME_RELEASE_URL"]["sync"] is False
