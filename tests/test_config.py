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


# LLM Configuration Tests


def test_llm_provider_default():
    """Test that LLM provider defaults to openai."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.llm_provider == "openai"


def test_llm_provider_from_env():
    """Test that LLM provider can be configured from environment."""
    with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic"}, clear=True):
        settings = Settings()
        assert settings.llm_provider == "anthropic"


def test_llm_provider_case_insensitive():
    """Test that LLM provider is case-insensitive."""
    with patch.dict(os.environ, {"LLM_PROVIDER": "OPENAI"}, clear=True):
        settings = Settings()
        assert settings.llm_provider == "openai"

    with patch.dict(os.environ, {"LLM_PROVIDER": "Anthropic"}, clear=True):
        settings = Settings()
        assert settings.llm_provider == "anthropic"


def test_llm_provider_invalid():
    """Test that invalid LLM provider raises ValueError."""
    import pytest
    from pydantic import ValidationError

    with patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}, clear=True):
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        assert "Invalid LLM provider" in str(exc_info.value)


def test_openai_model_default():
    """Test that OpenAI model defaults to gpt-5.1."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.openai_model == "gpt-5.1"


def test_openai_model_from_env():
    """Test that OpenAI model can be configured from environment."""
    with patch.dict(os.environ, {"OPENAI_MODEL": "gpt-4"}, clear=True):
        settings = Settings()
        assert settings.openai_model == "gpt-4"


def test_claude_model_default():
    """Test that Claude model defaults to claude-3-5-sonnet-20241022."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.claude_model == "claude-3-5-sonnet-20241022"


def test_claude_model_from_env():
    """Test that Claude model can be configured from environment."""
    with patch.dict(os.environ, {"CLAUDE_MODEL": "claude-opus-4"}, clear=True):
        settings = Settings()
        assert settings.claude_model == "claude-opus-4"


def test_system_prompt_path_default():
    """Test that system prompt path defaults to None."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.system_prompt_path is None


def test_system_prompt_path_from_env():
    """Test that system prompt path can be configured from environment."""
    with patch.dict(os.environ, {"SYSTEM_PROMPT_PATH": "/app/prompts/system.txt"}, clear=True):
        settings = Settings()
        assert settings.system_prompt_path == "/app/prompts/system.txt"


def test_llm_stub_mode_default():
    """Test that LLM stub mode defaults to False."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        assert settings.llm_stub_mode is False


def test_llm_stub_mode_from_env():
    """Test that LLM stub mode can be configured from environment."""
    with patch.dict(os.environ, {"LLM_STUB_MODE": "true"}, clear=True):
        settings = Settings()
        assert settings.llm_stub_mode is True

    with patch.dict(os.environ, {"LLM_STUB_MODE": "false"}, clear=True):
        settings = Settings()
        assert settings.llm_stub_mode is False


def test_validate_llm_config_openai_all_ok():
    """Test LLM config validation with valid OpenAI configuration."""
    env = {
        "LLM_PROVIDER": "openai",
        "OPENAI_MODEL": "gpt-5.1",
        "OPENAI_API_KEY": "sk-test-key",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        result = settings.validate_llm_config()
        assert result["provider"] == "ok"
        assert result["model"] == "ok"
        assert result["api_key"] == "ok"
        assert result["system_prompt"] == "using_default"


def test_validate_llm_config_anthropic_all_ok():
    """Test LLM config validation with valid Anthropic configuration."""
    env = {
        "LLM_PROVIDER": "anthropic",
        "CLAUDE_MODEL": "claude-3-5-sonnet-20241022",
        "CLAUDE_API_KEY": "sk-ant-test-key",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        result = settings.validate_llm_config()
        assert result["provider"] == "ok"
        assert result["model"] == "ok"
        assert result["api_key"] == "ok"
        assert result["system_prompt"] == "using_default"


def test_validate_llm_config_missing_api_key():
    """Test LLM config validation with missing API key."""
    with patch.dict(os.environ, {"LLM_PROVIDER": "openai"}, clear=True):
        settings = Settings()
        result = settings.validate_llm_config()
        assert result["api_key"] == "missing"


def test_validate_llm_config_with_prompt_file(tmp_path):
    """Test LLM config validation with existing prompt file."""
    prompt_file = tmp_path / "system.txt"
    prompt_file.write_text("Test system prompt")

    env = {
        "LLM_PROVIDER": "openai",
        "SYSTEM_PROMPT_PATH": str(prompt_file),
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        result = settings.validate_llm_config()
        assert result["system_prompt"] == "ok"


def test_validate_llm_config_prompt_file_not_found():
    """Test LLM config validation with non-existent prompt file."""
    env = {
        "LLM_PROVIDER": "openai",
        "SYSTEM_PROMPT_PATH": "/nonexistent/path/prompt.txt",
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        result = settings.validate_llm_config()
        assert result["system_prompt"] == "file_not_found"


def test_validate_llm_config_prompt_path_is_directory(tmp_path):
    """Test LLM config validation when prompt path is a directory."""
    env = {
        "LLM_PROVIDER": "openai",
        "SYSTEM_PROMPT_PATH": str(tmp_path),
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        result = settings.validate_llm_config()
        assert result["system_prompt"] == "not_a_file"


def test_validate_llm_config_prompt_file_empty(tmp_path):
    """Test LLM config validation with empty prompt file."""
    prompt_file = tmp_path / "empty.txt"
    prompt_file.write_text("")

    env = {
        "LLM_PROVIDER": "openai",
        "SYSTEM_PROMPT_PATH": str(prompt_file),
    }
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        result = settings.validate_llm_config()
        assert result["system_prompt"] == "empty_file"


def test_get_system_prompt_default():
    """Test getting default system prompt when no path configured."""
    with patch.dict(os.environ, {}, clear=True):
        settings = Settings()
        prompt = settings.get_system_prompt()
        assert prompt is not None
        assert len(prompt) > 0
        assert "AI assistant" in prompt or "specification" in prompt


def test_get_system_prompt_from_file(tmp_path):
    """Test loading system prompt from configured file."""
    prompt_file = tmp_path / "system.txt"
    expected_content = "Custom system prompt for testing"
    prompt_file.write_text(expected_content)

    env = {"SYSTEM_PROMPT_PATH": str(prompt_file)}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        prompt = settings.get_system_prompt()
        assert prompt == expected_content


def test_get_system_prompt_caching(tmp_path):
    """Test that system prompt is cached after first load."""
    prompt_file = tmp_path / "system.txt"
    prompt_file.write_text("Initial content")

    env = {"SYSTEM_PROMPT_PATH": str(prompt_file)}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()

        # First call loads from file
        prompt1 = settings.get_system_prompt()
        assert prompt1 == "Initial content"

        # Modify file
        prompt_file.write_text("Modified content")

        # Second call should return cached value
        prompt2 = settings.get_system_prompt()
        assert prompt2 == "Initial content"  # Still cached


def test_clear_prompt_cache(tmp_path):
    """Test clearing the prompt cache."""
    prompt_file = tmp_path / "system.txt"
    prompt_file.write_text("Initial content")

    env = {"SYSTEM_PROMPT_PATH": str(prompt_file)}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()

        # Load prompt
        prompt1 = settings.get_system_prompt()
        assert prompt1 == "Initial content"

        # Modify file and clear cache
        prompt_file.write_text("New content")
        settings.clear_prompt_cache()

        # Should reload from file
        prompt2 = settings.get_system_prompt()
        assert prompt2 == "New content"


def test_get_system_prompt_file_not_found():
    """Test fallback to default prompt when configured file doesn't exist."""
    env = {"SYSTEM_PROMPT_PATH": "/nonexistent/prompt.txt"}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        prompt = settings.get_system_prompt()
        # Should fall back to default
        assert prompt is not None
        assert len(prompt) > 0


def test_get_system_prompt_empty_file(tmp_path):
    """Test fallback to default when prompt file is empty."""
    prompt_file = tmp_path / "empty.txt"
    prompt_file.write_text("")

    env = {"SYSTEM_PROMPT_PATH": str(prompt_file)}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        prompt = settings.get_system_prompt()
        # Should fall back to default
        assert prompt is not None
        assert len(prompt) > 0


def test_get_system_prompt_read_error(tmp_path):
    """Test fallback to default when file cannot be read."""
    prompt_file = tmp_path / "system.txt"
    prompt_file.write_text("Test content")

    env = {"SYSTEM_PROMPT_PATH": str(prompt_file)}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()

        # Mock read_text to raise an exception
        def mock_read_text(*args, **kwargs):
            raise PermissionError("Permission denied")

        with patch("pathlib.Path.read_text", side_effect=mock_read_text):
            prompt = settings.get_system_prompt()
            # Should fall back to default
            assert prompt is not None
            assert len(prompt) > 0


def test_get_system_prompt_large_file(tmp_path):
    """Test that large prompt files are handled correctly."""
    prompt_file = tmp_path / "large.txt"
    # Create a large prompt (100KB)
    large_content = "A" * 100_000
    prompt_file.write_text(large_content)

    env = {"SYSTEM_PROMPT_PATH": str(prompt_file)}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        prompt = settings.get_system_prompt()
        assert len(prompt) == 100_000
        assert prompt == large_content


def test_get_system_prompt_file_too_large(tmp_path):
    """Test that oversized prompt files are rejected."""
    from spec_compiler.config import MAX_PROMPT_FILE_SIZE

    prompt_file = tmp_path / "huge.txt"
    # Create a file larger than MAX_PROMPT_FILE_SIZE
    huge_content = "A" * (MAX_PROMPT_FILE_SIZE + 1000)
    prompt_file.write_text(huge_content)

    env = {"SYSTEM_PROMPT_PATH": str(prompt_file)}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()
        prompt = settings.get_system_prompt()
        # Should fall back to default prompt
        assert "AI assistant" in prompt
        assert len(prompt) < 1000  # Default prompt is much smaller


def test_get_system_prompt_thread_safety(tmp_path):
    """Test that concurrent access to system prompt is thread-safe."""
    import threading

    prompt_file = tmp_path / "concurrent.txt"
    prompt_file.write_text("Thread-safe prompt content")

    env = {"SYSTEM_PROMPT_PATH": str(prompt_file)}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()

        results = []
        errors = []

        def load_prompt():
            try:
                result = settings.get_system_prompt()
                results.append(result)
            except Exception as e:
                errors.append(e)

        # Create multiple threads trying to load at the same time
        threads = [threading.Thread(target=load_prompt) for _ in range(10)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # All threads should get the same result
        assert len(errors) == 0
        assert len(results) == 10
        assert all(r == "Thread-safe prompt content" for r in results)


def test_clear_prompt_cache_thread_safety(tmp_path):
    """Test that cache clearing is thread-safe."""
    import threading

    prompt_file = tmp_path / "cache_clear.txt"
    prompt_file.write_text("Initial content")

    env = {"SYSTEM_PROMPT_PATH": str(prompt_file)}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()

        # Load initial prompt
        initial = settings.get_system_prompt()
        assert initial == "Initial content"

        errors = []

        def clear_and_reload():
            try:
                settings.clear_prompt_cache()
                settings.get_system_prompt()
            except Exception as e:
                errors.append(e)

        # Multiple threads clearing and reloading
        threads = [threading.Thread(target=clear_and_reload) for _ in range(5)]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Should not have any errors
        assert len(errors) == 0


def test_validate_prompt_path_security(tmp_path):
    """Test that path validation prevents directory traversal."""
    # Create a prompt file
    prompt_file = tmp_path / "legit.txt"
    prompt_file.write_text("Legitimate prompt")

    env = {"SYSTEM_PROMPT_PATH": str(prompt_file)}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()

        # Test with legitimate file
        from pathlib import Path

        is_valid, error = settings._validate_prompt_path(Path(str(prompt_file)))
        assert is_valid is True
        assert error is None


def test_validate_prompt_path_rejects_directory(tmp_path):
    """Test that directories are rejected as prompt paths."""
    env = {"SYSTEM_PROMPT_PATH": str(tmp_path)}
    with patch.dict(os.environ, env, clear=True):
        settings = Settings()

        from pathlib import Path

        is_valid, error = settings._validate_prompt_path(Path(str(tmp_path)))
        assert is_valid is False
        assert "not a regular file" in error.lower()
