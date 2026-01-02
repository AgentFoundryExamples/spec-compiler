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
Tests for compile endpoint LLM integration.

Validates the integration of LLM client into the compile endpoint,
including successful flows, error handling, and edge cases.
"""

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from spec_compiler.models import GitHubAuthToken, LlmResponseEnvelope
from spec_compiler.services.llm_client import LlmApiError


@pytest.fixture
def test_client_without_stub() -> TestClient:
    """
    Create a test client without stub mode for testing real LLM integration.

    Returns:
        TestClient instance with LLM stub mode disabled
    """
    from spec_compiler.app.main import create_app

    with (
        patch("spec_compiler.app.routes.compile.GitHubAuthClient") as mock_auth_class,
        patch("spec_compiler.app.routes.compile.GitHubRepoClient") as mock_repo_class,
        patch("spec_compiler.config.settings.llm_stub_mode", False),
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


def test_compile_with_stub_llm_client_success(test_client: TestClient) -> None:
    """Test successful compile flow with StubLlmClient."""
    payload = {
        "plan_id": "plan-stub-success",
        "spec_index": 0,
        "spec_data": {"type": "feature", "description": "Test feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["plan_id"] == "plan-stub-success"
    assert data["spec_index"] == 0


def test_compile_logs_llm_metrics(test_client: TestClient, caplog) -> None:
    """Test that LLM metrics are logged properly."""
    caplog.set_level(logging.INFO)

    payload = {
        "plan_id": "plan-metrics",
        "spec_index": 1,
        "spec_data": {"type": "bug", "description": "Fix issue"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202

    # Check that LLM metrics are logged
    log_messages = [record.message for record in caplog.records]
    assert any("llm_service_response_received" in msg for msg in log_messages)
    assert any("llm_response_parsed_successfully" in msg for msg in log_messages)
    assert any("compiled_version" in msg for msg in log_messages)
    assert any("compiled_issues_count" in msg for msg in log_messages)


def test_compile_with_llm_configuration_error(test_client_without_stub: TestClient) -> None:
    """Test that LLM configuration errors return 500."""
    # Without stub mode and without OPENAI_API_KEY, should get configuration error
    payload = {
        "plan_id": "plan-config-error",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client_without_stub.post("/compile-spec", json=payload)

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], dict)
    assert data["detail"]["error"] == "LLM service not configured"
    assert data["detail"]["plan_id"] == "plan-config-error"


def test_compile_with_llm_api_error_returns_503(test_client: TestClient) -> None:
    """Test that LLM API errors return 503."""
    payload = {
        "plan_id": "plan-api-error",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    # Mock the LLM client to raise an API error
    with patch("spec_compiler.services.llm_client.StubLlmClient") as mock_stub_class:
        mock_instance = MagicMock()
        mock_stub_class.return_value = mock_instance
        mock_instance.generate_response.side_effect = LlmApiError("API error")

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 503
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], dict)
        assert data["detail"]["error"] == "LLM service error"


def test_compile_with_malformed_llm_json_returns_500(test_client: TestClient) -> None:
    """Test that malformed JSON from LLM returns 500."""
    payload = {
        "plan_id": "plan-malformed-json",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    # Mock the LLM client to return invalid JSON
    with patch("spec_compiler.services.llm_client.StubLlmClient") as mock_stub_class:
        mock_instance = MagicMock()
        mock_stub_class.return_value = mock_instance

        # Return response with invalid JSON content
        invalid_response = LlmResponseEnvelope(
            request_id="test-request-id",
            status="success",
            content='{"invalid": "no version or issues"}',
            model="stub-model",
        )
        mock_instance.generate_response.return_value = invalid_response

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], dict)
        assert data["detail"]["error"] == "Invalid LLM response format"


def test_compile_logs_parsing_errors(test_client: TestClient, caplog) -> None:
    """Test that JSON parsing errors are logged with context."""
    caplog.set_level(logging.ERROR)

    payload = {
        "plan_id": "plan-parse-error",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    # Mock the LLM client to return invalid JSON
    with patch("spec_compiler.services.llm_client.StubLlmClient") as mock_stub_class:
        mock_instance = MagicMock()
        mock_stub_class.return_value = mock_instance

        invalid_response = LlmResponseEnvelope(
            request_id="test-request-id",
            status="success",
            content='not valid json at all',
            model="stub-model",
        )
        mock_instance.generate_response.return_value = invalid_response

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 500

        # Check that error was logged
        log_messages = [record.message for record in caplog.records]
        assert any("llm_response_parsing_failed" in msg for msg in log_messages)


def test_compile_builds_correct_llm_request_envelope(test_client: TestClient) -> None:
    """Test that LLM request envelope is built with correct data."""
    payload = {
        "plan_id": "plan-envelope-test",
        "spec_index": 2,
        "spec_data": {"type": "enhancement", "details": {"priority": "high"}},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    # Mock the LLM client to capture the request envelope
    captured_request = None

    with patch("spec_compiler.services.llm_client.StubLlmClient") as mock_stub_class:
        mock_instance = MagicMock()
        mock_stub_class.return_value = mock_instance

        def capture_request(request_envelope):
            nonlocal captured_request
            captured_request = request_envelope
            # Return valid response
            return LlmResponseEnvelope(
                request_id=request_envelope.request_id,
                status="success",
                content=json.dumps({
                    "version": "test/1.0",
                    "issues": [{"id": "TEST-1", "title": "Test"}]
                }),
                model="stub-model",
            )

        mock_instance.generate_response.side_effect = capture_request

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 202
        assert captured_request is not None
        assert captured_request.metadata["plan_id"] == "plan-envelope-test"
        assert captured_request.metadata["spec_index"] == 2
        assert captured_request.metadata["github_owner"] == "test-owner"
        assert captured_request.metadata["github_repo"] == "test-repo"
        assert captured_request.metadata["spec_data"] == payload["spec_data"]
        assert captured_request.repo_context is not None


def test_compile_with_missing_version_in_response(test_client: TestClient) -> None:
    """Test that LLM response without version field fails gracefully."""
    payload = {
        "plan_id": "plan-no-version",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    with patch("spec_compiler.services.llm_client.StubLlmClient") as mock_stub_class:
        mock_instance = MagicMock()
        mock_stub_class.return_value = mock_instance

        # Return response without version field
        invalid_response = LlmResponseEnvelope(
            request_id="test-request-id",
            status="success",
            content='{"issues": []}',  # Missing version
            model="stub-model",
        )
        mock_instance.generate_response.return_value = invalid_response

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "Invalid LLM response format"


def test_compile_with_missing_issues_in_response(test_client: TestClient) -> None:
    """Test that LLM response without issues field fails gracefully."""
    payload = {
        "plan_id": "plan-no-issues",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    with patch("spec_compiler.services.llm_client.StubLlmClient") as mock_stub_class:
        mock_instance = MagicMock()
        mock_stub_class.return_value = mock_instance

        # Return response without issues field
        invalid_response = LlmResponseEnvelope(
            request_id="test-request-id",
            status="success",
            content='{"version": "1.0"}',  # Missing issues
            model="stub-model",
        )
        mock_instance.generate_response.return_value = invalid_response

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "Invalid LLM response format"


def test_compile_with_empty_issues_array(test_client: TestClient) -> None:
    """Test that LLM response with empty issues array succeeds."""
    payload = {
        "plan_id": "plan-empty-issues",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    with patch("spec_compiler.services.llm_client.StubLlmClient") as mock_stub_class:
        mock_instance = MagicMock()
        mock_stub_class.return_value = mock_instance

        # Return response with empty issues array (valid)
        valid_response = LlmResponseEnvelope(
            request_id="test-request-id",
            status="success",
            content='{"version": "1.0", "issues": []}',
            model="stub-model",
        )
        mock_instance.generate_response.return_value = valid_response

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "accepted"


def test_compile_with_empty_llm_response_content(test_client: TestClient) -> None:
    """Test that empty LLM response content is caught and handled."""
    payload = {
        "plan_id": "plan-empty-content",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    with patch("spec_compiler.services.llm_client.StubLlmClient") as mock_stub_class:
        mock_instance = MagicMock()
        mock_stub_class.return_value = mock_instance

        # Return response with empty content
        empty_response = LlmResponseEnvelope(
            request_id="test-request-id",
            status="success",
            content="",
            model="stub-model",
        )
        mock_instance.generate_response.return_value = empty_response

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert data["detail"]["error"] == "Invalid LLM response format"


def test_compile_logs_compiled_spec_sample(test_client: TestClient, caplog) -> None:
    """Test that compiled spec sample is logged at debug level."""
    caplog.set_level(logging.DEBUG)

    payload = {
        "plan_id": "plan-debug-log",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202

    # Check that debug log contains compiled spec sample
    log_messages = [record.message for record in caplog.records if record.levelname == "DEBUG"]
    assert any("compiled_spec_sample" in msg for msg in log_messages)


def test_compile_with_unexpected_llm_exception(test_client: TestClient) -> None:
    """Test that unexpected exceptions from LLM client are handled gracefully."""
    payload = {
        "plan_id": "plan-unexpected-error",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    with patch("spec_compiler.services.llm_client.StubLlmClient") as mock_stub_class:
        mock_instance = MagicMock()
        mock_stub_class.return_value = mock_instance
        mock_instance.generate_response.side_effect = RuntimeError("Unexpected error")

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], dict)
        assert data["detail"]["error"] == "Unexpected LLM service error"


def test_compile_includes_repo_context_in_llm_request(test_client: TestClient) -> None:
    """Test that repository context is included in LLM request envelope."""
    payload = {
        "plan_id": "plan-repo-context",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    captured_request = None

    with patch("spec_compiler.services.llm_client.StubLlmClient") as mock_stub_class:
        mock_instance = MagicMock()
        mock_stub_class.return_value = mock_instance

        def capture_request(request_envelope):
            nonlocal captured_request
            captured_request = request_envelope
            return LlmResponseEnvelope(
                request_id=request_envelope.request_id,
                status="success",
                content=json.dumps({"version": "1.0", "issues": []}),
                model="stub-model",
            )

        mock_instance.generate_response.side_effect = capture_request

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 202
        assert captured_request is not None
        assert captured_request.repo_context is not None
        # Verify repo_context has the expected structure
        assert hasattr(captured_request.repo_context, "tree")
        assert hasattr(captured_request.repo_context, "dependencies")
        assert hasattr(captured_request.repo_context, "file_summaries")


def test_compile_with_unsupported_provider(test_client: TestClient) -> None:
    """Test that unsupported LLM provider triggers appropriate error."""
    payload = {
        "plan_id": "plan-unsupported-provider",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    # Mock settings to use an unsupported provider
    with patch("spec_compiler.config.settings.llm_provider", "unsupported_provider"):
        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert isinstance(data["detail"], dict)
        assert data["detail"]["error"] == "Failed to build LLM request"
