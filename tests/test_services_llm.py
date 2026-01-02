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

Tests the abstract LLM client interface, stub mode, OpenAI Responses client,
request assembly, error handling, and provider selection.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import httpx
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

    def test_generate_response_returns_sample_data(self) -> None:
        """Test that stub client returns parsed sample data."""
        client = StubLlmClient()
        request = LlmRequestEnvelope(request_id="test-req-123")

        response = client.generate_response(request)

        assert isinstance(response, LlmResponseEnvelope)
        assert response.request_id == "test-req-123"
        assert response.status == "success"
        assert response.model == "stub-model"
        assert response.content != ""
        assert response.usage is not None
        assert response.usage["total_tokens"] == 0
        assert response.metadata is not None
        assert response.metadata["stub_mode"] is True

    def test_generate_response_parses_sample_structure(self) -> None:
        """Test that stub client validates sample structure."""
        client = StubLlmClient()
        request = LlmRequestEnvelope(request_id="test-parse")

        response = client.generate_response(request)

        # Should have metadata from parsed output
        assert "version" in response.metadata
        assert "issue_count" in response.metadata
        assert response.metadata["version"] == "af/1.1"
        assert response.metadata["issue_count"] == 4

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
            organization_id="org-123",
            project_id="proj-456",
            max_retries=5,
            timeout=60.0,
        )
        assert client.organization_id == "org-123"
        assert client.project_id == "proj-456"
        assert client.max_retries == 5
        assert client.timeout == 60.0

    def test_build_headers_basic(self) -> None:
        """Test building basic HTTP headers."""
        client = OpenAiResponsesClient(api_key="test-key")
        headers = client._build_headers()

        assert headers["Authorization"] == "Bearer test-key"
        assert headers["Content-Type"] == "application/json"
        assert "OpenAI-Organization" not in headers
        assert "OpenAI-Project" not in headers

    def test_build_headers_with_org_and_project(self) -> None:
        """Test building headers with organization and project IDs."""
        client = OpenAiResponsesClient(
            api_key="test-key",
            organization_id="org-123",
            project_id="proj-456",
        )
        headers = client._build_headers()

        assert headers["Authorization"] == "Bearer test-key"
        assert headers["OpenAI-Organization"] == "org-123"
        assert headers["OpenAI-Project"] == "proj-456"

    def test_build_request_body_structure(self) -> None:
        """Test request body has correct Responses API structure."""
        client = OpenAiResponsesClient(api_key="test-key", model="gpt-5.1")

        request = LlmRequestEnvelope(
            request_id="req-123",
            system_prompt=SystemPromptConfig(template="Test prompt", max_tokens=1000),
            metadata={"spec_data": {"test": "data"}},
        )

        body = client._build_request_body(request)

        # Verify structure
        assert body["model"] == "gpt-5.1"
        assert "input" in body
        assert isinstance(body["input"], list)
        assert len(body["input"]) > 0
        assert body["input"][0]["role"] == "user"
        assert "content" in body["input"][0]
        assert isinstance(body["input"][0]["content"], list)
        assert body["input"][0]["content"][0]["type"] == "input_text"
        assert "text" in body["input"][0]["content"][0]
        assert body["response_format"] == {"type": "json_object"}
        assert body["max_output_tokens"] == 1000

    def test_parse_response_success(self) -> None:
        """Test parsing successful API response."""
        client = OpenAiResponsesClient(api_key="test-key")

        api_response = {
            "id": "resp_abc123",
            "object": "response",
            "created_at": 1234567890,
            "status": "completed",
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": '{"version": "1.0", "issues": []}'}
                    ],
                }
            ],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50,
            },
        }

        response = client._parse_response(api_response, "req-123")

        assert isinstance(response, LlmResponseEnvelope)
        assert response.request_id == "req-123"
        assert response.status == "success"
        assert response.content == '{"version": "1.0", "issues": []}'
        assert response.usage is not None
        assert response.usage["prompt_tokens"] == 100
        assert response.usage["completion_tokens"] == 50
        assert response.usage["total_tokens"] == 150
        assert response.metadata["response_id"] == "resp_abc123"

    def test_parse_response_with_no_output(self) -> None:
        """Test parsing response with missing output raises error."""
        client = OpenAiResponsesClient(api_key="test-key")

        api_response = {"id": "resp_123", "output": []}

        with pytest.raises(LlmApiError, match="contains no output"):
            client._parse_response(api_response, "req-123")

    def test_parse_response_with_no_content(self) -> None:
        """Test parsing response with missing content raises error."""
        client = OpenAiResponsesClient(api_key="test-key")

        api_response = {"output": [{"type": "message", "content": []}]}

        with pytest.raises(LlmApiError, match="contains no content"):
            client._parse_response(api_response, "req-123")

    @patch("httpx.Client")
    def test_make_request_with_retry_success(self, mock_client_class: Mock) -> None:
        """Test successful API request."""
        client = OpenAiResponsesClient(api_key="test-key")

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"output": "success"}

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        mock_client_class.return_value.__exit__.return_value = None

        headers = {"Authorization": "Bearer test-key"}
        body = {"model": "gpt-5.1"}

        result = client._make_request_with_retry(headers, body, "req-123")

        assert result == {"output": "success"}
        mock_client_instance.post.assert_called_once()

    @patch("httpx.Client")
    @patch("time.sleep")  # Mock sleep to avoid delays in tests
    def test_make_request_with_retry_on_server_error(
        self, mock_sleep: Mock, mock_client_class: Mock
    ) -> None:
        """Test retry on server error (5xx)."""
        client = OpenAiResponsesClient(api_key="test-key", max_retries=2)

        # First attempt returns 503, second attempt succeeds
        mock_response_error = Mock()
        mock_response_error.status_code = 503

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"output": "success"}

        mock_client_instance = MagicMock()
        mock_client_instance.post.side_effect = [mock_response_error, mock_response_success]
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        mock_client_class.return_value.__exit__.return_value = None

        headers = {"Authorization": "Bearer test-key"}
        body = {"model": "gpt-5.1"}

        result = client._make_request_with_retry(headers, body, "req-123")

        assert result == {"output": "success"}
        assert mock_client_instance.post.call_count == 2
        mock_sleep.assert_called_once()

    @patch("httpx.Client")
    def test_make_request_with_client_error_no_retry(self, mock_client_class: Mock) -> None:
        """Test that client errors (4xx) are not retried."""
        client = OpenAiResponsesClient(api_key="test-key", max_retries=3)

        # Mock 400 error
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad request", request=Mock(), response=mock_response
        )

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        mock_client_class.return_value.__exit__.return_value = None

        headers = {"Authorization": "Bearer test-key"}
        body = {"model": "gpt-5.1"}

        with pytest.raises(LlmApiError, match="Client error from OpenAI API"):
            client._make_request_with_retry(headers, body, "req-123")

        # Should only be called once (no retries on 4xx)
        mock_client_instance.post.assert_called_once()

    @patch("httpx.Client")
    @patch("time.sleep")
    def test_make_request_exhausts_retries(self, mock_sleep: Mock, mock_client_class: Mock) -> None:
        """Test that request fails after exhausting retries."""
        client = OpenAiResponsesClient(api_key="test-key", max_retries=3)

        # All attempts return 503
        mock_response = Mock()
        mock_response.status_code = 503

        mock_client_instance = MagicMock()
        mock_client_instance.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        mock_client_class.return_value.__exit__.return_value = None

        headers = {"Authorization": "Bearer test-key"}
        body = {"model": "gpt-5.1"}

        with pytest.raises(LlmApiError, match="failed after 3 attempts"):
            client._make_request_with_retry(headers, body, "req-123")

        assert mock_client_instance.post.call_count == 3

    @patch("httpx.Client")
    @patch("time.sleep")
    def test_make_request_with_timeout(self, mock_sleep: Mock, mock_client_class: Mock) -> None:
        """Test handling of timeout errors."""
        client = OpenAiResponsesClient(api_key="test-key", max_retries=2)

        mock_client_instance = MagicMock()
        mock_client_instance.post.side_effect = httpx.TimeoutException("Request timeout")
        mock_client_class.return_value.__enter__.return_value = mock_client_instance
        mock_client_class.return_value.__exit__.return_value = None

        headers = {"Authorization": "Bearer test-key"}
        body = {"model": "gpt-5.1"}

        with pytest.raises(LlmApiError, match="failed after 2 attempts"):
            client._make_request_with_retry(headers, body, "req-123")

        assert mock_client_instance.post.call_count == 2

    @patch("spec_compiler.services.openai_responses.OpenAiResponsesClient._make_request_with_retry")
    @patch("spec_compiler.services.openai_responses.OpenAiResponsesClient._parse_response")
    def test_generate_response_integration(self, mock_parse: Mock, mock_request: Mock) -> None:
        """Test full generate_response flow."""
        client = OpenAiResponsesClient(api_key="test-key", model="gpt-5.1")

        # Mock request and parse
        mock_request.return_value = {"output": "api response"}
        mock_parse.return_value = LlmResponseEnvelope(
            request_id="req-123",
            status="success",
            content="generated content",
            model="gpt-5.1",
            usage={"total_tokens": 150},
        )

        request = LlmRequestEnvelope(
            request_id="req-123",
            metadata={"spec_data": {}},
        )

        response = client.generate_response(request)

        assert response.request_id == "req-123"
        assert response.status == "success"
        assert response.content == "generated content"
        mock_request.assert_called_once()
        mock_parse.assert_called_once()


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

        client = create_llm_client(provider="openai")

        assert isinstance(client, OpenAiResponsesClient)

    @patch("spec_compiler.services.llm_client.settings")
    def test_create_client_anthropic_not_implemented(self, mock_settings: Mock) -> None:
        """Test that anthropic provider raises not implemented error."""
        mock_settings.llm_provider = "anthropic"
        mock_settings.llm_stub_mode = False

        with pytest.raises(LlmConfigurationError, match="not yet implemented"):
            create_llm_client()

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

        client = create_llm_client()
        request = LlmRequestEnvelope(request_id="factory-test")

        response = client.generate_response(request)

        assert response.request_id == "factory-test"
        assert response.status == "success"
        assert response.metadata["stub_mode"] is True
