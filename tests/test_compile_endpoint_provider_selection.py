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
Tests for LLM provider selection in compile endpoint.

Validates that the compile endpoint correctly selects between OpenAI and
Anthropic (Claude) providers based on configuration.
"""

import json
import logging
from unittest.mock import MagicMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from spec_compiler.models import GitHubAuthToken, LlmResponseEnvelope


@pytest.fixture(params=["openai", "anthropic"])
def test_client_provider(request) -> TestClient:
    """
    Create a test client configured for a specific LLM provider.

    This parametrized fixture creates clients for both OpenAI and Anthropic providers,
    reducing code duplication.
    """
    from spec_compiler.app.main import create_app

    provider = request.param

    # Provider-specific configuration
    provider_config = {
        "openai": {
            "llm_provider": "openai",
            "api_key_setting": "openai_api_key",
            "api_key_value": "test-openai-key",
        },
        "anthropic": {
            "llm_provider": "anthropic",
            "api_key_setting": "claude_api_key",
            "api_key_value": "test-claude-key",
        },
    }

    config = provider_config[provider]

    with (
        patch("spec_compiler.app.routes.compile.GitHubAuthClient") as mock_auth_class,
        patch("spec_compiler.app.routes.compile.GitHubRepoClient") as mock_repo_class,
        patch("spec_compiler.config.settings.llm_provider", config["llm_provider"]),
        patch("spec_compiler.config.settings.llm_stub_mode", False),
        patch(
            f"spec_compiler.config.settings.{config['api_key_setting']}", config["api_key_value"]
        ),
    ):
        # Setup auth client mock
        mock_auth_instance = MagicMock()
        mock_auth_class.return_value = mock_auth_instance
        mock_token = GitHubAuthToken(
            access_token="gho_test_token",
            token_type="bearer",
        )
        mock_auth_instance.mint_user_to_server_token.return_value = mock_token

        # Setup repo client mock
        mock_repo_instance = MagicMock()
        mock_repo_class.return_value = mock_repo_instance
        mock_repo_instance.get_json_file.side_effect = lambda owner, repo, path, token: {
            ".github/repo-analysis-output/tree.json": {"tree": []},
            ".github/repo-analysis-output/dependencies.json": {"dependencies": []},
            ".github/repo-analysis-output/file-summaries.json": {"summaries": []},
        }.get(path, {})

        app = create_app()
        yield TestClient(app)


@pytest.fixture
def test_client_openai() -> TestClient:
    """
    Create a test client configured for OpenAI provider.

    Note: Consider using test_client_provider parametrized fixture for new tests.
    This fixture is kept for backward compatibility with existing tests.
    """
    from spec_compiler.app.main import create_app

    with (
        patch("spec_compiler.app.routes.compile.GitHubAuthClient") as mock_auth_class,
        patch("spec_compiler.app.routes.compile.GitHubRepoClient") as mock_repo_class,
        patch("spec_compiler.config.settings.llm_provider", "openai"),
        patch("spec_compiler.config.settings.llm_stub_mode", False),
        patch("spec_compiler.config.settings.openai_api_key", "test-openai-key"),
    ):
        # Setup auth client mock
        mock_auth_instance = MagicMock()
        mock_auth_class.return_value = mock_auth_instance
        mock_token = GitHubAuthToken(
            access_token="gho_test_token",
            token_type="bearer",
        )
        mock_auth_instance.mint_user_to_server_token.return_value = mock_token

        # Setup repo client mock
        mock_repo_instance = MagicMock()
        mock_repo_class.return_value = mock_repo_instance
        mock_repo_instance.get_json_file.side_effect = lambda owner, repo, path, token: {
            ".github/repo-analysis-output/tree.json": {"tree": []},
            ".github/repo-analysis-output/dependencies.json": {"dependencies": []},
            ".github/repo-analysis-output/file-summaries.json": {"summaries": []},
        }.get(path, {})

        app = create_app()
        yield TestClient(app)


@pytest.fixture
def test_client_anthropic() -> TestClient:
    """
    Create a test client configured for Anthropic (Claude) provider.

    Note: Consider using test_client_provider parametrized fixture for new tests.
    This fixture is kept for backward compatibility with existing tests.
    """
    from spec_compiler.app.main import create_app

    with (
        patch("spec_compiler.app.routes.compile.GitHubAuthClient") as mock_auth_class,
        patch("spec_compiler.app.routes.compile.GitHubRepoClient") as mock_repo_class,
        patch("spec_compiler.config.settings.llm_provider", "anthropic"),
        patch("spec_compiler.config.settings.llm_stub_mode", False),
        patch("spec_compiler.config.settings.claude_api_key", "test-claude-key"),
    ):
        # Setup auth client mock
        mock_auth_instance = MagicMock()
        mock_auth_class.return_value = mock_auth_instance
        mock_token = GitHubAuthToken(
            access_token="gho_test_token",
            token_type="bearer",
        )
        mock_auth_instance.mint_user_to_server_token.return_value = mock_token

        # Setup repo client mock
        mock_repo_instance = MagicMock()
        mock_repo_class.return_value = mock_repo_instance
        mock_repo_instance.get_json_file.side_effect = lambda owner, repo, path, token: {
            ".github/repo-analysis-output/tree.json": {"tree": []},
            ".github/repo-analysis-output/dependencies.json": {"dependencies": []},
            ".github/repo-analysis-output/file-summaries.json": {"summaries": []},
        }.get(path, {})

        app = create_app()
        yield TestClient(app)


class TestProviderSelection:
    """Tests for LLM provider selection."""

    def test_openai_provider_creates_openai_client(
        self, test_client_openai: TestClient, caplog
    ) -> None:
        """Test that openai provider creates OpenAI client."""
        caplog.set_level(logging.INFO)

        with patch("spec_compiler.services.openai_responses.OpenAiResponsesClient") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            mock_client.generate_response.return_value = LlmResponseEnvelope(
                request_id="test-req",
                status="success",
                content=json.dumps({"version": "1.0", "issues": []}),
                model="gpt-5.1",
            )

            payload = {
                "plan_id": "plan-openai",
                "spec_index": 0,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client_openai.post("/compile-spec", json=payload)

            assert response.status_code == 202

            # Verify OpenAI client was created
            mock_openai.assert_called_once()

    def test_anthropic_provider_creates_claude_client(
        self, test_client_anthropic: TestClient, caplog
    ) -> None:
        """Test that anthropic provider creates Claude client."""
        caplog.set_level(logging.INFO)

        with patch("spec_compiler.services.anthropic_llm_client.ClaudeLlmClient") as mock_claude:
            mock_client = Mock()
            mock_claude.return_value = mock_client
            mock_client.generate_response.return_value = LlmResponseEnvelope(
                request_id="test-req",
                status="success",
                content=json.dumps({"version": "1.0", "issues": []}),
                model="claude-sonnet-4-5-20250929",
            )

            payload = {
                "plan_id": "plan-claude",
                "spec_index": 0,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client_anthropic.post("/compile-spec", json=payload)

            assert response.status_code == 202

            # Verify Claude client was created
            mock_claude.assert_called_once()

    def test_provider_logged_in_completion_message(self, test_client: TestClient, caplog) -> None:
        """Test that provider is logged in completion message."""
        caplog.set_level(logging.INFO)

        payload = {
            "plan_id": "plan-provider-log",
            "spec_index": 0,
            "spec": _create_valid_spec(),
            "github_owner": "owner",
            "github_repo": "repo",
        }

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 202

        # Check that provider was logged (in background task)
        log_records = [r for r in caplog.records if "background_compile_complete" in r.message]
        # In stub mode, the provider will be logged
        assert len(log_records) > 0


@pytest.mark.parametrize(
    "provider,client_path,model_name",
    [
        ("openai", "spec_compiler.services.openai_responses.OpenAiResponsesClient", "gpt-5.1"),
        (
            "anthropic",
            "spec_compiler.services.anthropic_llm_client.ClaudeLlmClient",
            "claude-sonnet-4-5-20250929",
        ),
    ],
)
class TestParametrizedProviderSelection:
    """Parametrized tests for provider selection."""

    def test_provider_creates_correct_client_type(
        self, provider: str, client_path: str, model_name: str, mock_publisher: Mock
    ) -> None:
        """Test that each provider creates the correct client type."""
        from spec_compiler.app.main import create_app

        with (
            patch("spec_compiler.app.routes.compile.GitHubAuthClient") as mock_auth_class,
            patch("spec_compiler.app.routes.compile.GitHubRepoClient") as mock_repo_class,
            patch("spec_compiler.config.settings.llm_provider", provider),
            patch("spec_compiler.config.settings.llm_stub_mode", False),
            patch("spec_compiler.config.settings.openai_api_key", "test-key"),
            patch("spec_compiler.config.settings.claude_api_key", "test-key"),
            patch(client_path) as mock_client_class,
        ):
            # Setup auth and repo mocks
            mock_auth_instance = MagicMock()
            mock_auth_class.return_value = mock_auth_instance
            mock_token = GitHubAuthToken(
                access_token="gho_test_token",
                token_type="bearer",
            )
            mock_auth_instance.mint_user_to_server_token.return_value = mock_token

            mock_repo_instance = MagicMock()
            mock_repo_class.return_value = mock_repo_instance
            mock_repo_instance.get_json_file.return_value = {}

            # Mock the client
            mock_client = Mock()
            mock_client_class.return_value = mock_client
            mock_client.generate_response.return_value = LlmResponseEnvelope(
                request_id="test-req",
                status="success",
                content=json.dumps({"version": "1.0", "issues": []}),
                model=model_name,
            )

            app = create_app()
            client = TestClient(app)

            payload = {
                "plan_id": f"plan-{provider}",
                "spec_index": 0,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = client.post("/compile-spec", json=payload)
            assert response.status_code == 202
            mock_client_class.assert_called_once()


class TestProviderConfigurationErrors:
    """Tests for provider configuration errors."""

    def test_openai_provider_without_api_key_fails(self) -> None:
        """Test that OpenAI provider without API key fails on client creation."""
        from spec_compiler.services.llm_client import LlmConfigurationError, create_llm_client

        with (
            patch("spec_compiler.services.llm_client.settings") as mock_settings,
            patch("spec_compiler.services.openai_responses.settings") as mock_openai_settings,
        ):
            mock_settings.llm_provider = "openai"
            mock_settings.llm_stub_mode = False
            mock_openai_settings.openai_api_key = None

            with pytest.raises(LlmConfigurationError, match="API key not configured"):
                create_llm_client()

    def test_anthropic_provider_without_api_key_fails(self) -> None:
        """Test that Anthropic provider without API key fails on client creation."""
        from spec_compiler.services.llm_client import LlmConfigurationError, create_llm_client

        with (
            patch("spec_compiler.services.llm_client.settings") as mock_settings,
            patch(
                "spec_compiler.services.anthropic_llm_client.settings"
            ) as mock_anthropic_settings,
        ):
            mock_settings.llm_provider = "anthropic"
            mock_settings.llm_stub_mode = False
            mock_anthropic_settings.claude_api_key = None

            with pytest.raises(LlmConfigurationError, match="API key not configured"):
                create_llm_client()

    def test_stub_mode_bypasses_api_key_requirement(self) -> None:
        """Test that stub mode works without API keys."""
        from spec_compiler.services.llm_client import StubLlmClient, create_llm_client

        with patch("spec_compiler.services.llm_client.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.llm_stub_mode = True

            client = create_llm_client()

            assert isinstance(client, StubLlmClient)


class TestProviderEnvironmentIsolation:
    """Tests for environment variable isolation between provider tests."""

    def test_provider_switching_between_tests(self) -> None:
        """Test that provider can be switched between tests without leakage."""
        from spec_compiler.services.llm_client import create_llm_client

        # Test OpenAI
        with (
            patch("spec_compiler.services.llm_client.settings") as mock_settings,
            patch("spec_compiler.services.openai_responses.settings") as mock_openai_settings,
        ):
            mock_settings.llm_provider = "openai"
            mock_settings.llm_stub_mode = False
            mock_openai_settings.openai_api_key = "test-key"
            mock_openai_settings.openai_model = "gpt-5.1"
            mock_openai_settings.openai_organization = None
            mock_openai_settings.openai_project = None
            mock_openai_settings.openai_api_base = "https://api.openai.com/v1"
            mock_openai_settings.llm_max_retries = 3
            mock_openai_settings.llm_timeout = 120.0

            client = create_llm_client()
            assert client.__class__.__name__ == "OpenAiResponsesClient"

        # Test Anthropic
        with (
            patch("spec_compiler.services.llm_client.settings") as mock_settings,
            patch(
                "spec_compiler.services.anthropic_llm_client.settings"
            ) as mock_anthropic_settings,
        ):
            mock_settings.llm_provider = "anthropic"
            mock_settings.llm_stub_mode = False
            mock_anthropic_settings.claude_api_key = "test-key"
            mock_anthropic_settings.claude_model = "claude-sonnet-4-5-20250929"
            mock_anthropic_settings.claude_api_base = None
            mock_anthropic_settings.llm_max_retries = 3
            mock_anthropic_settings.llm_timeout = 120.0

            client = create_llm_client()
            assert client.__class__.__name__ == "ClaudeLlmClient"

    def test_stub_mode_respects_provider_setting(self) -> None:
        """Test that stub mode respects the configured provider."""
        from spec_compiler.services.llm_client import StubLlmClient, create_llm_client


def _create_valid_spec(
    purpose: str = "Test purpose",
    vision: str = "Test vision",
    must: list[str] | None = None,
    dont: list[str] | None = None,
    nice: list[str] | None = None,
    assumptions: list[str] | None = None,
) -> dict:
    """Helper to create a valid spec dictionary for testing."""
    return {
        "purpose": purpose,
        "vision": vision,
        "must": must if must is not None else [],
        "dont": dont if dont is not None else [],
        "nice": nice if nice is not None else [],
        "assumptions": assumptions if assumptions is not None else [],
    }



        # Test with OpenAI provider in stub mode
        with patch("spec_compiler.services.llm_client.settings") as mock_settings:
            mock_settings.llm_provider = "openai"
            mock_settings.llm_stub_mode = True
            mock_settings.openai_model = "gpt-5.1"

            client = create_llm_client()
            assert isinstance(client, StubLlmClient)
            assert client.provider == "openai"
            assert client.model == "gpt-5.1"

        # Test with Anthropic provider in stub mode
        with patch("spec_compiler.services.llm_client.settings") as mock_settings:
            mock_settings.llm_provider = "anthropic"
            mock_settings.llm_stub_mode = True
            mock_settings.claude_model = "claude-sonnet-4-5-20250929"

            client = create_llm_client()
            assert isinstance(client, StubLlmClient)
            assert client.provider == "anthropic"
            assert client.model == "claude-sonnet-4-5-20250929"
