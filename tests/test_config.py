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


def test_github_api_base_url_default():
    """Test that GitHub API base URL has a sensible default."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.github_api_base_url == "https://api.github.com"


def test_github_api_base_url_from_env():
    """Test that GitHub API base URL can be overridden."""
    with patch.dict(
        os.environ, {"GITHUB_API_BASE_URL": "https://github.example.com/api"}, clear=True
    ):
        settings = Settings()
        assert settings.github_api_base_url == "https://github.example.com/api"


def test_minting_service_base_url_default():
    """Test that minting service base URL defaults to None."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.minting_service_base_url is None


def test_minting_service_base_url_from_env():
    """Test that minting service base URL can be configured."""
    url = "https://token-service-xxxxx-uc.a.run.app"
    with patch.dict(os.environ, {"MINTING_SERVICE_BASE_URL": url}, clear=True):
        settings = Settings()
        assert settings.minting_service_base_url == url


def test_minting_service_auth_header_default():
    """Test that minting service auth header defaults to None."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.minting_service_auth_header is None


def test_minting_service_auth_header_from_env():
    """Test that minting service auth header can be configured."""
    with patch.dict(os.environ, {"MINTING_SERVICE_AUTH_HEADER": "Bearer token123"}, clear=True):
        settings = Settings()
        assert settings.minting_service_auth_header == "Bearer token123"


def test_validate_github_config_all_valid():
    """Test GitHub config validation with all valid settings."""
    env = {
        "GITHUB_API_BASE_URL": "https://api.github.com",
        "MINTING_SERVICE_BASE_URL": "https://token-service.run.app",
        "MINTING_SERVICE_AUTH_HEADER": "Bearer token",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        result = settings.validate_github_config()
        assert result["github_api_url"] == "ok"
        assert result["minting_service_url"] == "ok"
        assert result["minting_auth_configured"] == "yes"


def test_validate_github_config_missing_minting_url():
    """Test GitHub config validation with missing minting service URL."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        result = settings.validate_github_config()
        assert result["github_api_url"] == "ok"  # Has default
        assert result["minting_service_url"] == "missing"
        assert result["minting_auth_configured"] == "no"


def test_validate_github_config_invalid_github_url():
    """Test GitHub config validation with invalid GitHub URL."""
    with patch.dict(os.environ, {"GITHUB_API_BASE_URL": "ftp://invalid.com"}, clear=True):
        settings = Settings()
        result = settings.validate_github_config()
        assert result["github_api_url"] == "invalid"


def test_validate_github_config_invalid_minting_url():
    """Test GitHub config validation with invalid minting service URL."""
    with patch.dict(os.environ, {"MINTING_SERVICE_BASE_URL": "not-a-url"}, clear=True):
        settings = Settings()
        result = settings.validate_github_config()
        assert result["minting_service_url"] == "invalid"


def test_validate_github_config_empty_strings():
    """Test GitHub config validation with empty string URLs."""
    env = {
        "GITHUB_API_BASE_URL": "   ",
        "MINTING_SERVICE_BASE_URL": "",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        result = settings.validate_github_config()
        assert result["github_api_url"] == "missing"
        assert result["minting_service_url"] == "missing"
