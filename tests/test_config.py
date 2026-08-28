from app.core.config import Settings


def test_default_settings_are_valid() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_name == "Tributarius prudens"
    assert settings.database_url.startswith("sqlite")
