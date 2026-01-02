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

import logging
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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

    # LLM Configuration
    llm_provider: str = Field(
        default="openai",
        description="LLM provider to use (openai|anthropic)",
    )
    openai_model: str = Field(
        default="gpt-5.1",
        description="OpenAI model to use for compilations",
    )
    claude_model: str = Field(
        default="claude-sonnet-4.5",
        description="Anthropic Claude model to use for compilations",
    )
    system_prompt_path: str | None = Field(
        default=None,
        description="Path to system prompt file. If not set, uses default prompt.",
    )
    llm_stub_mode: bool = Field(
        default=False,
        description="Enable stub mode to bypass actual LLM API calls for testing",
    )

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
        if not self.github_api_base_url.strip():
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

    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """
        Validate LLM provider is one of the supported values.

        Args:
            v: The provider value to validate

        Returns:
            The validated provider value (lowercased)

        Raises:
            ValueError: If provider is not supported
        """
        v_lower = v.lower().strip()
        if v_lower not in ("openai", "anthropic"):
            raise ValueError(f"Invalid LLM provider '{v}'. Must be 'openai' or 'anthropic'.")
        return v_lower

    def validate_llm_config(self) -> dict[str, str]:
        """
        Validate LLM configuration and return status.

        Returns:
            Dictionary with validation results for LLM configuration.
            Keys: 'provider', 'model', 'api_key', 'system_prompt'
            Values: 'ok', 'missing', 'invalid', or specific status
        """
        result: dict[str, str] = {}

        # Validate provider (already validated by field_validator, but check anyway)
        if self.llm_provider.lower() in ("openai", "anthropic"):
            result["provider"] = "ok"
        else:
            result["provider"] = "invalid"

        # Validate model is set
        if self.llm_provider.lower() == "openai":
            result["model"] = "ok" if self.openai_model.strip() else "missing"
        elif self.llm_provider.lower() == "anthropic":
            result["model"] = "ok" if self.claude_model.strip() else "missing"
        else:
            result["model"] = "unknown_provider"

        # Validate API key is configured (warn if missing, but don't block startup)
        if self.llm_provider.lower() == "openai":
            result["api_key"] = "ok" if self.openai_api_key else "missing"
        elif self.llm_provider.lower() == "anthropic":
            result["api_key"] = "ok" if self.claude_api_key else "missing"
        else:
            result["api_key"] = "unknown_provider"

        # Validate system prompt path if configured
        if self.system_prompt_path:
            prompt_path = Path(self.system_prompt_path)
            if not prompt_path.exists():
                result["system_prompt"] = "file_not_found"
            elif not prompt_path.is_file():
                result["system_prompt"] = "not_a_file"
            elif not prompt_path.stat().st_size:
                result["system_prompt"] = "empty_file"
            else:
                result["system_prompt"] = "ok"
        else:
            result["system_prompt"] = "using_default"

        return result

    _system_prompt_cache: str | None = None

    def get_system_prompt(self) -> str:
        """
        Load and return the system prompt content.

        If system_prompt_path is configured, loads from that file (with caching).
        Otherwise, returns a default system prompt.

        Returns:
            The system prompt content as a string

        Raises:
            RuntimeError: If configured prompt file cannot be read
        """
        # Return cached prompt if available
        if self._system_prompt_cache is not None:
            return self._system_prompt_cache

        # If path is configured, try to load from file
        if self.system_prompt_path:
            try:
                prompt_path = Path(self.system_prompt_path)
                if not prompt_path.exists():
                    logger.warning(
                        f"System prompt file not found at {self.system_prompt_path}, "
                        "using default prompt"
                    )
                    self._system_prompt_cache = self._get_default_system_prompt()
                    return self._system_prompt_cache

                # Read the file content
                content = prompt_path.read_text(encoding="utf-8")
                if not content.strip():
                    logger.warning(
                        f"System prompt file at {self.system_prompt_path} is empty, "
                        "using default prompt"
                    )
                    self._system_prompt_cache = self._get_default_system_prompt()
                    return self._system_prompt_cache

                logger.info(
                    f"Loaded system prompt from {self.system_prompt_path} "
                    f"({len(content)} characters)"
                )
                self._system_prompt_cache = content
                return self._system_prompt_cache

            except Exception as e:
                logger.error(
                    f"Failed to read system prompt from {self.system_prompt_path}: {e}. "
                    "Using default prompt."
                )
                self._system_prompt_cache = self._get_default_system_prompt()
                return self._system_prompt_cache

        # No path configured, use default
        self._system_prompt_cache = self._get_default_system_prompt()
        return self._system_prompt_cache

    def _get_default_system_prompt(self) -> str:
        """
        Return the default system prompt when no custom prompt is configured.

        Returns:
            Default system prompt text
        """
        return (
            "You are an AI assistant that helps compile and process specifications. "
            "Analyze the provided specification data and generate appropriate responses "
            "based on the context and requirements."
        )

    def clear_prompt_cache(self) -> None:
        """
        Clear the cached system prompt.

        Useful for testing or when prompt file has been updated and needs to be reloaded.
        """
        self._system_prompt_cache = None


# Global settings instance
settings = Settings()
