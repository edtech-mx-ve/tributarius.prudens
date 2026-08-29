from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración validada de la aplicación."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Tributarius prudens"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", pattern="^(development|test|production)$")
    log_level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    enable_docs: bool = True
    database_url: str = "sqlite:///./tributarius.db"
    trusted_hosts_csv: str = "127.0.0.1,localhost,testserver"
    max_request_body_bytes: int = Field(default=1_048_576, ge=16_384, le=8_388_608)
    consultation_rate_limit: int = Field(default=30, ge=1, le=1_000)
    consultation_rate_window_seconds: int = Field(default=60, ge=1, le=3_600)
    deployment_platform: str = Field(default="local", pattern="^(local|render)$")
    runtime_profile: str = Field(
        default="development", pattern="^(development|stateless_free)$"
    )
    rag_artifact_dir: str = "deployment/runtime_artifacts_semantic_v2"
    require_rag_artifacts: bool = False
    rag_local_files_only: bool = True
    verify_rag_integrity: bool = True
    legal_retrieval_policy_path: str = "app/resources/legal_retrieval_policy.json"
    runtime_rule_set_path: str = "rules/examples/basic_obligations.json"
    temporal_provenance_registry_path: str = (
        "knowledge/temporal/temporal_provenance_registry.json"
    )
    require_temporal_provenance_registry: bool = False

    def trusted_hosts(self) -> list[str]:
        """Hosts permitidos, normalizados desde una variable de entorno simple."""
        hosts = [item.strip() for item in self.trusted_hosts_csv.split(",") if item.strip()]
        if not hosts:
            raise ValueError("TRUSTED_HOSTS_CSV debe contener al menos un host.")
        return hosts


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia cacheada de configuración."""
    return Settings()
