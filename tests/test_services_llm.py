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
Tests for LLM client services.

Tests the abstract LLM client interface, stub mode, OpenAI Chat Completions client,
request assembly, error handling, and provider selection.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from spec_compiler.models.llm import LlmRequestEnvelope, LlmResponseEnvelope, SystemPromptConfig
from spec_compiler.services.llm_client import (
    LlmApiError,
    LlmConfigurationError,
    StubLlmClient,
    create_llm_client,
)
from spec_compiler.services.openai_responses import OpenAiResponsesClient


class TestStubLlmClient:
    """Tests for StubLlmClient."""

    def test_initialization_with_default_path(self) -> None:
        """Test that stub client initializes with default sample path."""
        client = StubLlmClient()
        assert client.sample_file_path is not None
        assert "sample.v1_1.json" in client.sample_file_path

    def test_initialization_with_custom_path(self) -> None:
        """Test that stub client accepts custom sample path."""
        custom_path = "/custom/path/sample.json"
        client = StubLlmClient(sample_file_path=custom_path)
        assert client.sample_file_path == custom_path

    def test_initialization_with_provider_and_model(self) -> None:
        """Test that stub client accepts provider and model parameters."""
        client = StubLlmClient(provider="anthropic", model="claude-3-5-sonnet-20241022")
        assert client.provider == "anthropic"
        assert client.model == "claude-3-5-sonnet-20241022"

    @patch("spec_compiler.services.llm_client.settings")
    def test_initialization_uses_settings_for_provider_and_model(self, mock_settings: Mock) -> None:
        """Test that stub client uses settings when provider/model not provided."""
        mock_settings.llm_provider = "openai"
        mock_settings.openai_model = "gpt-5.1"
        mock_settings.claude_model = "claude-3-5-sonnet-20241022"

        client = StubLlmClient()

        assert client.provider == "openai"
        assert client.model == "gpt-5.1"

    @patch("spec_compiler.services.llm_client.settings")
    def test_generate_response_returns_sample_data(self, mock_settings: Mock) -> None:
        """Test that stub client returns parsed sample data."""
        mock_settings.llm_provider = "openai"
        mock_settings.openai_model = "gpt-5.1"

        client = StubLlmClient()
        request = LlmRequestEnvelope(request_id="test-req-123")

        response = client.generate_response(request)

        assert isinstance(response, LlmResponseEnvelope)
        assert response.request_id == "test-req-123"
        assert response.status == "success"
        assert response.model == "gpt-5.1"
        assert response.content != ""
        assert response.usage is not None
        assert response.usage["total_tokens"] == 0
        assert response.metadata is not None
        assert response.metadata["stub_mode"] is True
        assert response.metadata["provider"] == "openai"

    @patch("spec_compiler.services.llm_client.settings")
    def test_generate_response_parses_sample_structure(self, mock_settings: Mock) -> None:
        """Test that stub client validates sample structure."""
        mock_settings.llm_provider = "openai"
        mock_settings.openai_model = "gpt-5.1"

        client = StubLlmClient()
        request = LlmRequestEnvelope(request_id="test-parse")

        response = client.generate_response(request)

        # Should have metadata from parsed output
        assert "version" in response.metadata
        assert "issue_count" in response.metadata
        assert "provider" in response.metadata
        assert response.metadata["version"] == "af/1.1"
        assert response.metadata["issue_count"] == 4
        assert response.metadata["provider"] == "openai"

    def test_generate_response_with_anthropic_provider(self) -> None:
        """Test that stub client uses Anthropic model when provider is anthropic."""
        client = StubLlmClient(provider="anthropic", model="claude-3-5-sonnet-20241022")
        request = LlmRequestEnvelope(request_id="test-anthropic")

        response = client.generate_response(request)

        assert response.model == "claude-3-5-sonnet-20241022"
        assert response.metadata["provider"] == "anthropic"

    def test_generate_response_with_missing_file(self) -> None:
        """Test that missing sample file raises error."""
        client = StubLlmClient(sample_file_path="/nonexistent/file.json")
        request = LlmRequestEnvelope(request_id="test-missing")

        with pytest.raises(LlmApiError, match="Sample file not found"):
            client.generate_response(request)

    def test_generate_response_with_directory_path(self) -> None:
        """Test that directory path raises error."""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            client = StubLlmClient(sample_file_path=tmpdir)
            request = LlmRequestEnvelope(request_id="test-dir")

            with pytest.raises(LlmApiError, match="not a file"):
                client.generate_response(request)

    def test_generate_response_with_invalid_json(self) -> None:
        """Test that invalid JSON in sample file raises error."""
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write("invalid json {")
            tmp_path = tmp.name

        try:
            client = StubLlmClient(sample_file_path=tmp_path)
            request = LlmRequestEnvelope(request_id="test-invalid")

            with pytest.raises(LlmApiError, match="Failed to read or parse sample file"):
                client.generate_response(request)
        finally:
            Path(tmp_path).unlink()


class TestOpenAiResponsesClient:
    """Tests for OpenAiResponsesClient."""

    def test_initialization_with_api_key(self) -> None:
        """Test client initialization with API key."""
        client = OpenAiResponsesClient(api_key="test-key-123", model="gpt-5.1")
        assert client.api_key == "test-key-123"
        assert client.model == "gpt-5.1"
        assert client.max_retries == 3
        assert client.timeout == 120.0

    def test_initialization_without_api_key_raises_error(self) -> None:
        """Test that missing API key raises configuration error."""
        with patch("spec_compiler.services.openai_responses.settings") as mock_settings:
            mock_settings.openai_api_key = None
            mock_settings.openai_model = "gpt-5.1"

            with pytest.raises(LlmConfigurationError, match="API key not configured"):
                OpenAiResponsesClient()

    def test_initialization_with_custom_parameters(self) -> None:
        """Test client initialization with custom parameters."""
        client = OpenAiResponsesClient(
            api_key="key",
            model="custom-model",
            organization="org-123",
            project="proj-456",
            max_retries=5,
            timeout=60.0,
        )
        assert client.organization == "org-123"
        assert client.project == "proj-456"
        assert client.max_retries == 5
        assert client.timeout == 60.0

    def test_build_request_params_structure(self) -> None:
        """Test request params have correct Chat Completions API structure."""
        client = OpenAiResponsesClient(api_key="test-key", model="gpt-5.1")

        request = LlmRequestEnvelope(
            request_id="req-123",
            system_prompt=SystemPromptConfig(template="Test prompt", max_tokens=1000),
            metadata={"spec_data": {"test": "data"}},
        )

        params = client._build_request_params(request)

        # Verify structure
        assert params["model"] == "gpt-5.1"
        assert "messages" in params
        assert isinstance(params["messages"], list)
        assert len(params["messages"]) == 2  # system + user messages
        assert params["messages"][0]["role"] == "system"
        assert params["messages"][0]["content"] == "Test prompt"
        assert params["messages"][1]["role"] == "user"
        assert "content" in params["messages"][1]
        assert params["response_format"] == {"type": "json_object"}
        assert params["max_tokens"] == 1000

    def test_parse_response_success(self) -> None:
        """Test parsing successful API response."""
        from openai.types.chat import ChatCompletion
        from openai.types.chat.chat_completion import Choice
        from openai.types.chat.chat_completion_message import ChatCompletionMessage
        from openai.types.completion_usage import CompletionUsage

        client = OpenAiResponsesClient(api_key="test-key")

        # Create mock ChatCompletion response
        api_response = ChatCompletion(
            id="chatcmpl_abc123",
            object="chat.completion",
            created=1234567890,
            model="gpt-5.1",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(
                        role="assistant",
                        content='{"version": "1.0", "issues": []}',
                    ),
                    finish_reason="stop",
                )
            ],
            usage=CompletionUsage(
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
            ),
        )

        response = client._parse_response(api_response, "req-123")

        assert isinstance(response, LlmResponseEnvelope)
        assert response.request_id == "req-123"
        assert response.status == "success"
        assert response.content == '{"version": "1.0", "issues": []}'
        assert response.usage is not None
        assert response.usage["prompt_tokens"] == 100
        assert response.usage["completion_tokens"] == 50
        assert response.usage["total_tokens"] == 150
        assert response.metadata["response_id"] == "chatcmpl_abc123"
        assert response.metadata["provider"] == "openai"

    def test_parse_response_with_no_choices(self) -> None:
        assert response.content == '{"version": "1.0", "issues": []}'
        assert response.usage is not None
        assert response.usage["prompt_tokens"] == 100
        assert response.usage["completion_tokens"] == 50
        assert response.usage["total_tokens"] == 150
        assert response.metadata["response_id"] == "resp_abc123"

    def test_parse_response_with_no_choices(self) -> None:
        """Test parsing response with missing choices raises error."""
        from openai.types.chat import ChatCompletion

        client = OpenAiResponsesClient(api_key="test-key")

        api_response = ChatCompletion(
            id="chatcmpl_123",
            object="chat.completion",
            created=1234567890,
            model="gpt-5.1",
            choices=[],
        )

        with pytest.raises(LlmApiError, match="contains no choices"):
            client._parse_response(api_response, "req-123")

    def test_parse_response_with_no_content(self) -> None:
        """Test parsing response with missing content raises error."""
        from openai.types.chat import ChatCompletion
        from openai.types.chat.chat_completion import Choice
        from openai.types.chat.chat_completion_message import ChatCompletionMessage

        client = OpenAiResponsesClient(api_key="test-key")

        api_response = ChatCompletion(
            id="chatcmpl_123",
            object="chat.completion",
            created=1234567890,
            model="gpt-5.1",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content=None),
                    finish_reason="stop",
                )
            ],
        )

        with pytest.raises(LlmApiError, match="contains no message content"):
            client._parse_response(api_response, "req-123")

    @patch("time.sleep")
    def test_make_request_with_retry_success(self, mock_sleep: Mock) -> None:
        """Test successful API request using SDK."""
        from openai.types.chat import ChatCompletion
        from openai.types.chat.chat_completion import Choice
        from openai.types.chat.chat_completion_message import ChatCompletionMessage
        from openai.types.completion_usage import CompletionUsage

        client = OpenAiResponsesClient(api_key="test-key")

        # Mock successful response
        mock_response = ChatCompletion(
            id="chatcmpl_abc",
            object="chat.completion",
            created=1234567890,
            model="gpt-5.1",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content="test response"),
                    finish_reason="stop",
                )
            ],
            usage=CompletionUsage(prompt_tokens=10, completion_tokens=5, total_tokens=15),
        )

        with patch.object(
            client.client.chat.completions, "create", return_value=mock_response
        ) as mock_create:
            request_params = {"model": "gpt-5.1", "messages": []}

            result = client._make_request_with_retry(request_params, "req-123")

            assert result == mock_response
            mock_create.assert_called_once_with(**request_params)
            mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_make_request_with_retry_on_rate_limit(self, mock_sleep: Mock) -> None:
        """Test retry on rate limit error."""
        from openai import RateLimitError
        from openai.types.chat import ChatCompletion
        from openai.types.chat.chat_completion import Choice
        from openai.types.chat.chat_completion_message import ChatCompletionMessage

        client = OpenAiResponsesClient(api_key="test-key", max_retries=2)

        # Create mock response for successful attempt
        mock_response = ChatCompletion(
            id="chatcmpl_abc",
            object="chat.completion",
            created=1234567890,
            model="gpt-5.1",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content="test"),
                    finish_reason="stop",
                )
            ],
        )

        # First attempt raises RateLimitError, second succeeds
        rate_limit_error = RateLimitError(
            "Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit"}},
        )

        with patch.object(
            client.client.chat.completions,
            "create",
            side_effect=[rate_limit_error, mock_response],
        ):
            request_params = {"model": "gpt-5.1", "messages": []}

            result = client._make_request_with_retry(request_params, "req-123")

            assert result == mock_response
            mock_sleep.assert_called_once()

    @patch("time.sleep")
    def test_make_request_with_client_error_no_retry(self, mock_sleep: Mock) -> None:
        """Test that client errors (4xx) are not retried."""
        from openai import APIError

        client = OpenAiResponsesClient(api_key="test-key", max_retries=3)

        # Create APIError with 400 status code
        api_error = APIError(
            "Bad request",
            request=Mock(),
            body={"error": {"message": "Bad request"}},
        )
        api_error.status_code = 400

        with patch.object(
            client.client.chat.completions,
            "create",
            side_effect=api_error,
        ):
            request_params = {"model": "gpt-5.1", "messages": []}

            with pytest.raises(LlmApiError, match="Client error from OpenAI API"):
                client._make_request_with_retry(request_params, "req-123")

            # Should only be called once (no retries on 4xx)
            mock_sleep.assert_not_called()

    @patch("time.sleep")
    def test_make_request_exhausts_retries(self, mock_sleep: Mock) -> None:
        """Test that request fails after exhausting retries."""
        from openai import APITimeoutError

        client = OpenAiResponsesClient(api_key="test-key", max_retries=3)

        # All attempts raise timeout
        with patch.object(
            client.client.chat.completions,
            "create",
            side_effect=APITimeoutError("Timeout"),
        ):
            request_params = {"model": "gpt-5.1", "messages": []}

            with pytest.raises(LlmApiError, match="failed after 3 attempts"):
                client._make_request_with_retry(request_params, "req-123")

            # Sleep should be called twice (between attempts 1-2 and 2-3)
            assert mock_sleep.call_count == 2

    @patch("time.sleep")
    def test_make_request_with_timeout(self, mock_sleep: Mock) -> None:
        """Test handling of timeout errors."""
        from openai import APITimeoutError

        client = OpenAiResponsesClient(api_key="test-key", max_retries=2)

        with patch.object(
            client.client.chat.completions,
            "create",
            side_effect=APITimeoutError("Request timeout"),
        ):
            request_params = {"model": "gpt-5.1", "messages": []}

            with pytest.raises(LlmApiError, match="failed after 2 attempts"):
                client._make_request_with_retry(request_params, "req-123")

            assert mock_sleep.call_count == 1

    def test_generate_response_integration(self) -> None:
        """Test full generate_response flow."""
        from openai.types.chat import ChatCompletion
        from openai.types.chat.chat_completion import Choice
        from openai.types.chat.chat_completion_message import ChatCompletionMessage
        from openai.types.completion_usage import CompletionUsage

        client = OpenAiResponsesClient(api_key="test-key", model="gpt-5.1")

        # Mock successful API response
        mock_response = ChatCompletion(
            id="chatcmpl_abc",
            object="chat.completion",
            created=1234567890,
            model="gpt-5.1",
            choices=[
                Choice(
                    index=0,
                    message=ChatCompletionMessage(role="assistant", content="generated content"),
                    finish_reason="stop",
                )
            ],
            usage=CompletionUsage(prompt_tokens=100, completion_tokens=50, total_tokens=150),
        )

        with patch.object(client.client.chat.completions, "create", return_value=mock_response):
            request = LlmRequestEnvelope(
                request_id="req-123",
                metadata={"spec_data": {}},
            )

            response = client.generate_response(request)

            assert response.request_id == "req-123"
            assert response.status == "success"
            assert response.content == "generated content"
            assert response.metadata["provider"] == "openai"
            assert "latency_ms" in response.metadata


class TestCreateLlmClient:
    """Tests for create_llm_client factory function."""

    @patch("spec_compiler.services.llm_client.settings")
    def test_create_stub_client_when_stub_mode_enabled(self, mock_settings: Mock) -> None:
        """Test that stub client is created when stub mode is enabled."""
        mock_settings.llm_provider = "openai"
        mock_settings.llm_stub_mode = True

        client = create_llm_client()

        assert isinstance(client, StubLlmClient)

    @patch("spec_compiler.services.llm_client.settings")
    def test_create_stub_client_with_explicit_stub_mode(self, mock_settings: Mock) -> None:
        """Test that explicit stub_mode=True creates stub client."""
        mock_settings.llm_provider = "openai"
        mock_settings.llm_stub_mode = False

        client = create_llm_client(stub_mode=True)

        assert isinstance(client, StubLlmClient)

    @patch("spec_compiler.services.openai_responses.settings")
    @patch("spec_compiler.services.llm_client.settings")
    def test_create_openai_client_when_provider_is_openai(
        self, mock_llm_settings: Mock, mock_openai_settings: Mock
    ) -> None:
        """Test that OpenAI client is created for openai provider."""
        mock_llm_settings.llm_provider = "openai"
        mock_llm_settings.llm_stub_mode = False
        mock_openai_settings.openai_api_key = "test-key"
        mock_openai_settings.openai_model = "gpt-5.1"
        mock_openai_settings.openai_api_base = None
        mock_openai_settings.openai_organization = None
        mock_openai_settings.openai_project = None
        mock_openai_settings.llm_timeout = 120.0
        mock_openai_settings.llm_max_retries = 3

        client = create_llm_client()

        assert isinstance(client, OpenAiResponsesClient)

    @patch("spec_compiler.services.openai_responses.settings")
    @patch("spec_compiler.services.llm_client.settings")
    def test_create_client_with_explicit_provider(
        self, mock_llm_settings: Mock, mock_openai_settings: Mock
    ) -> None:
        """Test creating client with explicit provider parameter."""
        mock_llm_settings.llm_stub_mode = False
        mock_openai_settings.openai_api_key = "test-key"
        mock_openai_settings.openai_model = "gpt-5.1"
        mock_openai_settings.openai_api_base = None
        mock_openai_settings.openai_organization = None
        mock_openai_settings.openai_project = None
        mock_openai_settings.llm_timeout = 120.0
        mock_openai_settings.llm_max_retries = 3

        client = create_llm_client(provider="openai")

        assert isinstance(client, OpenAiResponsesClient)

    @patch("spec_compiler.services.anthropic_llm_client.settings")
    @patch("spec_compiler.services.llm_client.settings")
    def test_create_client_anthropic(
        self, mock_llm_settings: Mock, mock_anthropic_settings: Mock
    ) -> None:
        """Test that Anthropic client is created for anthropic provider."""
        from spec_compiler.services.anthropic_llm_client import ClaudeLlmClient

        mock_llm_settings.llm_provider = "anthropic"
        mock_llm_settings.llm_stub_mode = False
        mock_anthropic_settings.claude_api_key = "test-key"
        mock_anthropic_settings.claude_model = "claude-3-5-sonnet-20241022"
        mock_anthropic_settings.claude_api_base = None
        mock_anthropic_settings.llm_timeout = 120.0
        mock_anthropic_settings.llm_max_retries = 3

        client = create_llm_client()

        assert isinstance(client, ClaudeLlmClient)

    @patch("spec_compiler.services.llm_client.settings")
    def test_create_client_unknown_provider(self, mock_settings: Mock) -> None:
        """Test that unknown provider raises error."""
        mock_settings.llm_provider = "unknown"
        mock_settings.llm_stub_mode = False

        with pytest.raises(LlmConfigurationError, match="Unknown LLM provider"):
            create_llm_client()

    @patch("spec_compiler.services.openai_responses.settings")
    @patch("spec_compiler.services.llm_client.settings")
    def test_create_client_provider_case_insensitive(
        self, mock_llm_settings: Mock, mock_openai_settings: Mock
    ) -> None:
        """Test that provider comparison is case insensitive."""
        mock_llm_settings.llm_stub_mode = False
        mock_openai_settings.openai_api_key = "test-key"
        mock_openai_settings.openai_model = "gpt-5.1"
        mock_openai_settings.openai_api_base = None
        mock_openai_settings.openai_organization = None
        mock_openai_settings.openai_project = None
        mock_openai_settings.llm_timeout = 120.0
        mock_openai_settings.llm_max_retries = 3

        client = create_llm_client(provider="OpenAI")

        assert isinstance(client, OpenAiResponsesClient)


class TestLlmClientIntegration:
    """Integration tests for LLM client components."""

    def test_stub_client_returns_valid_llm_response(self) -> None:
        """Test that stub client returns structurally valid response."""
        client = StubLlmClient()
        request = LlmRequestEnvelope(request_id="integration-test")

        response = client.generate_response(request)

        # Verify response structure
        assert isinstance(response, LlmResponseEnvelope)
        assert response.request_id == "integration-test"
        assert response.status == "success"
        assert response.content != ""
        assert response.model is not None
        assert response.usage is not None
        assert response.metadata is not None

        # Verify content can be parsed as LlmCompiledSpecOutput
        from spec_compiler.models.llm import LlmCompiledSpecOutput

        compiled = LlmCompiledSpecOutput.from_json_string(response.content)
        assert compiled.version is not None
        assert isinstance(compiled.issues, list)

    @patch("spec_compiler.services.llm_client.settings")
    def test_factory_creates_working_stub_client(self, mock_settings: Mock) -> None:
        """Test that factory-created stub client works correctly."""
        mock_settings.llm_provider = "openai"
        mock_settings.llm_stub_mode = True
        mock_settings.openai_model = "gpt-5.1"

        client = create_llm_client()
        request = LlmRequestEnvelope(request_id="factory-test")

        response = client.generate_response(request)

        assert response.request_id == "factory-test"
        assert response.status == "success"
        assert response.metadata["stub_mode"] is True
        assert response.metadata["provider"] == "openai"
