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
Tests for Anthropic Claude LLM client.

Tests the ClaudeLlmClient implementation including initialization,
request building, response parsing, error handling, and retry logic.
"""

from unittest.mock import Mock, patch

import pytest
from anthropic import APIError, APITimeoutError, RateLimitError
from anthropic.types import Message, Usage
from anthropic.types.content_block import ContentBlock

from spec_compiler.models.llm import LlmRequestEnvelope, LlmResponseEnvelope, SystemPromptConfig
from spec_compiler.services.anthropic_llm_client import ClaudeLlmClient
from spec_compiler.services.llm_client import LlmApiError, LlmConfigurationError


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




class TestClaudeLlmClient:
    """Tests for ClaudeLlmClient."""

    def test_initialization_with_api_key(self) -> None:
        """Test client initialization with API key."""
        client = ClaudeLlmClient(api_key="test-key-123", model="claude-sonnet-4-5-20250929")
        assert client.api_key == "test-key-123"
        assert client.model == "claude-sonnet-4-5-20250929"
        assert client.max_retries == 3
        assert client.timeout == 120.0

    def test_initialization_without_api_key_raises_error(self) -> None:
        """Test that missing API key raises configuration error."""
        with patch("spec_compiler.services.anthropic_llm_client.settings") as mock_settings:
            mock_settings.claude_api_key = None
            mock_settings.claude_model = "claude-sonnet-4-5-20250929"

            with pytest.raises(LlmConfigurationError, match="API key not configured"):
                ClaudeLlmClient()

    def test_initialization_with_custom_parameters(self) -> None:
        """Test client initialization with custom parameters."""
        client = ClaudeLlmClient(
            api_key="key",
            model="custom-model",
            max_retries=5,
            timeout=60.0,
        )
        assert client.max_retries == 5
        assert client.timeout == 60.0

    def test_initialization_uses_default_model_from_settings(self) -> None:
        """Test that client uses Sonnet 4.5 default model from settings when none provided."""
        with patch("spec_compiler.services.anthropic_llm_client.settings") as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-sonnet-4-5-20250929"
            mock_settings.claude_api_base = None
            mock_settings.llm_max_retries = 3
            mock_settings.llm_timeout = 120.0

            client = ClaudeLlmClient()
            
            assert client.model == "claude-sonnet-4-5-20250929"
            assert client.api_key == "test-key"

    def test_sdk_request_payload_uses_default_model(self) -> None:
        """Test that SDK request payload contains default Sonnet 4.5 model when no override provided."""
        with patch("spec_compiler.services.anthropic_llm_client.settings") as mock_settings:
            mock_settings.claude_api_key = "test-key"
            mock_settings.claude_model = "claude-sonnet-4-5-20250929"
            mock_settings.claude_api_base = None
            mock_settings.llm_max_retries = 3
            mock_settings.llm_timeout = 120.0

            client = ClaudeLlmClient()
            
            # Mock successful response
            mock_content = Mock(spec=ContentBlock)
            mock_content.text = '{"version": "1.0", "issues": []}'
            
            mock_usage = Mock(spec=Usage)
            mock_usage.input_tokens = 100
            mock_usage.output_tokens = 50
            
            mock_response = Mock(spec=Message)
            mock_response.id = "msg_123"
            mock_response.content = [mock_content]
            mock_response.model = "claude-sonnet-4-5-20250929"
            mock_response.role = "assistant"
            mock_response.stop_reason = "end_turn"
            mock_response.usage = mock_usage

            with patch.object(client.client.messages, "create", return_value=mock_response) as mock_create:
                request = LlmRequestEnvelope(
                    request_id="req-123",
                    system_prompt=SystemPromptConfig(template="Test prompt", max_tokens=1000),
                    metadata={"spec": _create_valid_spec()},
                )
                
                client.generate_response(request)
                
                # Verify that messages.create was called with the default model in the payload
                mock_create.assert_called_once()
                call_kwargs = mock_create.call_args[1]
                assert call_kwargs["model"] == "claude-sonnet-4-5-20250929"
                assert "messages" in call_kwargs
                assert call_kwargs["system"] == "Test prompt"

    def test_build_request_payload_structure(self) -> None:
        """Test request payload has correct Messages API structure."""
        client = ClaudeLlmClient(api_key="test-key", model="claude-sonnet-4-5-20250929")

        request = LlmRequestEnvelope(
            request_id="req-123",
            system_prompt=SystemPromptConfig(template="Test prompt", max_tokens=1000),
            metadata={"spec": _create_valid_spec()},
        )

        payload = client._build_request_payload(request)

        # Verify structure
        assert payload["model"] == "claude-sonnet-4-5-20250929"
        assert "messages" in payload
        assert isinstance(payload["messages"], list)
        assert len(payload["messages"]) > 0
        assert payload["messages"][0]["role"] == "user"
        assert "content" in payload["messages"][0]
        assert payload["system"] == "Test prompt"
        assert payload["max_tokens"] == 1000

    def test_build_request_payload_uses_default_system_prompt(self) -> None:
        """Test that default system prompt is used when not provided."""
        client = ClaudeLlmClient(api_key="test-key", model="claude-sonnet-4-5-20250929")

        with patch("spec_compiler.services.anthropic_llm_client.settings") as mock_settings:
            # Create a mock object that has the get_system_prompt method
            mock_settings.get_system_prompt = Mock(return_value="Default system prompt")

            request = LlmRequestEnvelope(
                request_id="req-123",
                system_prompt=SystemPromptConfig(template="", max_tokens=2048),
                metadata={"spec": _create_valid_spec()},
            )

            payload = client._build_request_payload(request)

            assert payload["system"] == "Default system prompt"
            mock_settings.get_system_prompt.assert_called_once()

    def test_parse_response_success(self) -> None:
        """Test parsing successful API response."""
        client = ClaudeLlmClient(api_key="test-key")

        # Create mock content block
        mock_content = Mock(spec=ContentBlock)
        mock_content.text = '{"version": "1.0", "issues": []}'

        # Create mock usage
        mock_usage = Mock(spec=Usage)
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50

        # Create mock message
        api_response = Mock(spec=Message)
        api_response.id = "msg_abc123"
        api_response.content = [mock_content]
        api_response.model = "claude-sonnet-4-5-20250929"
        api_response.role = "assistant"
        api_response.stop_reason = "end_turn"
        api_response.usage = mock_usage

        response = client._parse_response(api_response, "req-123")

        assert isinstance(response, LlmResponseEnvelope)
        assert response.request_id == "req-123"
        assert response.status == "success"
        assert response.content == '{"version": "1.0", "issues": []}'
        assert response.usage is not None
        assert response.usage["prompt_tokens"] == 100
        assert response.usage["completion_tokens"] == 50
        assert response.usage["total_tokens"] == 150
        assert response.metadata["response_id"] == "msg_abc123"
        assert response.metadata["provider"] == "anthropic"
        assert response.metadata["stop_reason"] == "end_turn"

    def test_parse_response_with_no_content(self) -> None:
        """Test parsing response with missing content raises error."""
        client = ClaudeLlmClient(api_key="test-key")

        api_response = Mock(spec=Message)
        api_response.content = []

        with pytest.raises(LlmApiError, match="contains no content"):
            client._parse_response(api_response, "req-123")

    def test_parse_response_with_no_text(self) -> None:
        """Test parsing response with content but no text raises error."""
        client = ClaudeLlmClient(api_key="test-key")

        # Mock content block without text attribute
        mock_content = Mock(spec=ContentBlock)
        del mock_content.text  # Remove text attribute

        api_response = Mock(spec=Message)
        api_response.content = [mock_content]

        with pytest.raises(LlmApiError, match="contains no text"):
            client._parse_response(api_response, "req-123")

    @patch("spec_compiler.services.anthropic_llm_client.time.sleep")
    def test_make_request_with_retry_success(self, mock_sleep: Mock) -> None:
        """Test successful API request."""
        client = ClaudeLlmClient(api_key="test-key")

        # Mock successful response
        mock_content = Mock(spec=ContentBlock)
        mock_content.text = "Test response"

        mock_usage = Mock(spec=Usage)
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 5

        mock_response = Mock(spec=Message)
        mock_response.id = "msg_123"
        mock_response.content = [mock_content]
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.role = "assistant"
        mock_response.stop_reason = "end_turn"
        mock_response.usage = mock_usage

        with patch.object(client.client.messages, "create", return_value=mock_response):
            request_params = {
                "model": "claude-sonnet-4-5-20250929",
                "messages": [{"role": "user", "content": "test"}],
                "system": "test system",
                "max_tokens": 1024,
            }

            result = client._make_request_with_retry(request_params, "req-123")

            assert result == mock_response
            # Sleep should not be called on first successful attempt
            mock_sleep.assert_not_called()

    @patch("spec_compiler.services.anthropic_llm_client.time.sleep")
    def test_make_request_with_retry_on_rate_limit(self, mock_sleep: Mock) -> None:
        """Test retry on rate limit error."""
        client = ClaudeLlmClient(api_key="test-key", max_retries=2)

        # Mock successful response for second attempt
        mock_content = Mock(spec=ContentBlock)
        mock_content.text = "Test response"

        mock_usage = Mock(spec=Usage)
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 5

        mock_response = Mock(spec=Message)
        mock_response.id = "msg_123"
        mock_response.content = [mock_content]
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.role = "assistant"
        mock_response.stop_reason = "end_turn"
        mock_response.usage = mock_usage

        # Create proper RateLimitError
        rate_limit_error = RateLimitError(
            "Rate limit exceeded",
            response=Mock(status_code=429),
            body={"error": {"message": "Rate limit"}},
        )

        # First attempt raises RateLimitError, second succeeds
        with patch.object(
            client.client.messages,
            "create",
            side_effect=[rate_limit_error, mock_response],
        ):
            request_params = {
                "model": "claude-sonnet-4-5-20250929",
                "messages": [{"role": "user", "content": "test"}],
                "system": "test",
                "max_tokens": 1024,
            }

            result = client._make_request_with_retry(request_params, "req-123")

            assert result == mock_response
            # Sleep should be called once for retry backoff
            mock_sleep.assert_called_once()

    @patch("spec_compiler.services.anthropic_llm_client.time.sleep")
    def test_make_request_with_retry_exhausted(self, mock_sleep: Mock) -> None:
        """Test that retries are exhausted and error is raised."""
        client = ClaudeLlmClient(api_key="test-key", max_retries=2)

        # All attempts raise timeout
        with patch.object(
            client.client.messages,
            "create",
            side_effect=APITimeoutError("Timeout"),
        ):
            request_params = {
                "model": "claude-sonnet-4-5-20250929",
                "messages": [{"role": "user", "content": "test"}],
                "system": "test",
                "max_tokens": 1024,
            }

            with pytest.raises(LlmApiError, match="failed after 2 attempts"):
                client._make_request_with_retry(request_params, "req-123")

            # Sleep should be called once (between attempt 1 and 2)
            assert mock_sleep.call_count == 1

    @patch("spec_compiler.services.anthropic_llm_client.time.sleep")
    def test_make_request_client_error_no_retry(self, mock_sleep: Mock) -> None:
        """Test that client errors (4xx) are not retried."""
        client = ClaudeLlmClient(api_key="test-key", max_retries=3)

        # Create proper APIError with status_code
        api_error = APIError(
            "Client error",
            request=Mock(),
            body={"error": {"message": "Bad request"}},
        )
        api_error.status_code = 400

        with patch.object(
            client.client.messages,
            "create",
            side_effect=api_error,
        ):
            request_params = {
                "model": "claude-sonnet-4-5-20250929",
                "messages": [{"role": "user", "content": "test"}],
                "system": "test",
                "max_tokens": 1024,
            }

            with pytest.raises(LlmApiError, match="Client error from Anthropic API"):
                client._make_request_with_retry(request_params, "req-123")

            # Sleep should not be called for client errors
            mock_sleep.assert_not_called()

    def test_generate_response_includes_latency(self) -> None:
        """Test that generate_response includes latency metrics."""
        client = ClaudeLlmClient(api_key="test-key")

        # Mock successful response
        mock_content = Mock(spec=ContentBlock)
        mock_content.text = '{"version": "1.0", "issues": []}'

        mock_usage = Mock(spec=Usage)
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50

        mock_response = Mock(spec=Message)
        mock_response.id = "msg_123"
        mock_response.content = [mock_content]
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.role = "assistant"
        mock_response.stop_reason = "end_turn"
        mock_response.usage = mock_usage

        with patch.object(client.client.messages, "create", return_value=mock_response):
            request = LlmRequestEnvelope(
                request_id="req-123",
                system_prompt=SystemPromptConfig(template="Test", max_tokens=1000),
                metadata={"spec": _create_valid_spec()},
            )

            response = client.generate_response(request)

            assert response.metadata is not None
            assert "latency_ms" in response.metadata
            # Just verify latency_ms exists and is a positive number
            assert response.metadata["latency_ms"] > 0
            assert response.metadata["provider"] == "anthropic"

    def test_generate_response_logs_provider_and_model(self) -> None:
        """Test that generate_response logs provider and model information."""
        client = ClaudeLlmClient(api_key="test-key", model="claude-sonnet-4-5-20250929")

        # Mock successful response
        mock_content = Mock(spec=ContentBlock)
        mock_content.text = '{"version": "1.0", "issues": []}'

        mock_usage = Mock(spec=Usage)
        mock_usage.input_tokens = 100
        mock_usage.output_tokens = 50

        mock_response = Mock(spec=Message)
        mock_response.id = "msg_123"
        mock_response.content = [mock_content]
        mock_response.model = "claude-sonnet-4-5-20250929"
        mock_response.role = "assistant"
        mock_response.stop_reason = "end_turn"
        mock_response.usage = mock_usage

        with patch.object(client.client.messages, "create", return_value=mock_response):
            with patch("spec_compiler.services.anthropic_llm_client.logger") as mock_logger:
                request = LlmRequestEnvelope(
                    request_id="req-123",
                    system_prompt=SystemPromptConfig(template="Test", max_tokens=1000),
                    metadata={"spec": _create_valid_spec()},
                )

                client.generate_response(request)

                # Check that logs contain provider and model info
                log_calls = [str(call) for call in mock_logger.info.call_args_list]
                log_text = " ".join(log_calls)
                assert "anthropic" in log_text.lower()
                assert "claude-sonnet-4-5-20250929" in log_text

    def test_generate_response_handles_api_error(self) -> None:
        """Test that generate_response properly wraps API errors."""
        client = ClaudeLlmClient(api_key="test-key")

        # Create proper APIError
        api_error = APIError(
            "API error",
            request=Mock(),
            body={"error": {"message": "API error"}},
        )

        with patch.object(
            client.client.messages,
            "create",
            side_effect=api_error,
        ):
            request = LlmRequestEnvelope(
                request_id="req-123",
                system_prompt=SystemPromptConfig(template="Test", max_tokens=1000),
                metadata={"spec": _create_valid_spec()},
            )

            with pytest.raises(LlmApiError):
                client.generate_response(request)
