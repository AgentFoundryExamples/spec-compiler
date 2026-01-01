"""
Tests for configuration management.

Validates the Settings class and environment variable handling.
"""

import os
from unittest.mock import patch

from spec_compiler.config import Settings


def test_settings_defaults():
    """Test that settings have sensible defaults."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()

        assert settings.app_env == "development"
        assert settings.port == 8080
        assert settings.openai_api_key is None
        assert settings.claude_api_key is None
        assert settings.gcp_project_id is None
        assert settings.cors_origins == ""
        assert settings.log_level == "INFO"
        assert settings.log_json is True


def test_settings_from_env():
    """Test that settings are loaded from environment variables."""
    env = {
        "APP_ENV": "production",
        "PORT": "9000",
        "OPENAI_API_KEY": "test-key",
        "CLAUDE_API_KEY": "test-claude-key",
        "GCP_PROJECT_ID": "test-project",
        "CORS_ORIGINS": "http://example.com,http://test.com",
        "LOG_LEVEL": "DEBUG",
        "LOG_JSON": "false",
    }

    with patch.dict(os.environ, env, clear=True):
        settings = Settings()

        assert settings.app_env == "production"
        assert settings.port == 9000
        assert settings.openai_api_key == "test-key"
        assert settings.claude_api_key == "test-claude-key"
        assert settings.gcp_project_id == "test-project"
        assert settings.cors_origins == "http://example.com,http://test.com"
        assert settings.log_level == "DEBUG"
        assert settings.log_json is False


def test_cors_origins_list_wildcard():
    """Test that wildcard CORS origins are handled correctly."""
    with patch.dict(os.environ, {"CORS_ORIGINS": "*"}, clear=True):
        settings = Settings()
        assert settings.cors_origins_list == ["*"]


def test_cors_origins_list_empty():
    """Test that empty CORS origins string returns empty list."""
    with patch.dict(os.environ, {"CORS_ORIGINS": ""}, clear=True):
        settings = Settings()
        assert settings.cors_origins_list == []


def test_cors_origins_list_comma_separated():
    """Test that comma-separated CORS origins are parsed correctly."""
    with patch.dict(os.environ, {"CORS_ORIGINS": "http://example.com,http://test.com"}, clear=True):
        settings = Settings()
        assert settings.cors_origins_list == ["http://example.com", "http://test.com"]


def test_cors_origins_list_with_spaces():
    """Test that CORS origins with spaces are trimmed."""
    with patch.dict(
        os.environ,
        {"CORS_ORIGINS": "http://example.com , http://test.com , http://third.com"},
        clear=True,
    ):
        settings = Settings()
        assert settings.cors_origins_list == [
            "http://example.com",
            "http://test.com",
            "http://third.com",
        ]


def test_is_production():
    """Test is_production property."""
    with patch.dict(os.environ, {"APP_ENV": "production"}, clear=True):
        settings = Settings()
        assert settings.is_production is True
        assert settings.is_development is False


def test_is_development():
    """Test is_development property."""
    with patch.dict(os.environ, {"APP_ENV": "development"}, clear=True):
        settings = Settings()
        assert settings.is_production is False
        assert settings.is_development is True


def test_case_insensitive_env():
    """Test that environment variables are case-insensitive."""
    with patch.dict(os.environ, {"app_env": "staging"}, clear=True):
        settings = Settings()
        assert settings.app_env == "staging"
