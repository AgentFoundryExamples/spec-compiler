"""
Configuration module for spec-compiler service.

Manages environment variables and application settings using Pydantic BaseSettings.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All settings have sensible defaults where safe to prevent boot failures.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application Environment
    app_env: str = Field(default="development", description="Application environment")
    port: int = Field(default=8080, description="Server port")

    # API Keys - Optional to allow service to start without them
    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    claude_api_key: str | None = Field(default=None, description="Anthropic Claude API key")

    # Google Cloud Configuration
    gcp_project_id: str | None = Field(default=None, description="GCP Project ID")
    pubsub_topic_plan_status: str | None = Field(
        default=None, description="Pub/Sub topic for plan status updates"
    )
    downstream_log_sink: str | None = Field(
        default=None, description="Downstream log sink for Cloud Logging"
    )

    # CORS Configuration
    cors_origins: str = Field(
        default="*",
        description="Comma-separated list of allowed CORS origins, or * for all",
    )

    # Application Version
    app_version: str = Field(default="0.1.0", description="Application version")

    # Request ID Header
    request_id_header: str = Field(
        default="X-Request-Id", description="Header name for request correlation"
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    log_json: bool = Field(default=True, description="Enable JSON structured logging for Cloud Run")

    @property
    def cors_origins_list(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        if not self.cors_origins or self.cors_origins.strip() == "":
            return []
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env.lower() == "development"


# Global settings instance
settings = Settings()
