# Copyright 2025 John Brosnihan
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
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
        default="",
        description="Comma-separated list of allowed CORS origins",
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

    # Request Body Limits
    max_request_body_size_bytes: int = Field(
        default=10_485_760,  # 10MB default
        description="Maximum request body size in bytes",
        gt=0,
    )

    # Idempotency Key Limits
    max_idempotency_key_length: int = Field(
        default=100,
        description="Maximum idempotency key length for security",
        gt=0,
    )

    # GitHub API Configuration
    github_api_base_url: str = Field(
        default="https://api.github.com",
        description="Base URL for GitHub API",
    )

    # GitHub Token Minting Service Configuration
    minting_service_base_url: str | None = Field(
        default=None,
        description="Base URL for GitHub token minting service (Cloud Run service URL)",
    )
    minting_service_auth_header: str | None = Field(
        default=None,
        description="Optional authorization header value for minting service (GCP identity token)",
    )

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

    def validate_github_config(self) -> dict[str, str | None]:
        """
        Validate GitHub configuration and return status.

        Returns:
            Dictionary with validation results for GitHub API and minting service URLs.
            Keys: 'github_api_url', 'minting_service_url', 'minting_auth_configured'
            Values: 'ok', 'missing', 'invalid', or URL/status string
        """
        result: dict[str, str | None] = {}

        # Validate GitHub API URL
        if not self.github_api_base_url or not self.github_api_base_url.strip():
            result["github_api_url"] = "missing"
        elif not self.github_api_base_url.startswith(("http://", "https://")):
            result["github_api_url"] = "invalid"
        else:
            result["github_api_url"] = "ok"

        # Validate minting service URL
        if not self.minting_service_base_url or not self.minting_service_base_url.strip():
            result["minting_service_url"] = "missing"
        elif not self.minting_service_base_url.startswith(("http://", "https://")):
            result["minting_service_url"] = "invalid"
        else:
            result["minting_service_url"] = "ok"

        # Check auth header configuration
        result["minting_auth_configured"] = "yes" if self.minting_service_auth_header else "no"

        return result


# Global settings instance
settings = Settings()
