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
Tests for compile endpoint with repository context integration.

Validates the integration of GitHubAuthClient and GitHubRepoClient
into the compile endpoint, including token minting, file fetching,
fallback handling, and error scenarios.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from spec_compiler.models import GitHubAuthToken
from spec_compiler.services.github_auth import MintingError
from spec_compiler.services.github_repo import GitHubFileError, InvalidJSONError


@pytest.fixture
def mock_github_auth_client():
    """Mock GitHubAuthClient for testing."""
    with patch("spec_compiler.app.routes.compile.GitHubAuthClient") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance

        # Default behavior: successful token minting
        mock_token = GitHubAuthToken(
            access_token="gho_test_token_123",
            token_type="bearer",
            expires_at="2025-12-31T23:59:59+00:00",
        )
        mock_instance.mint_user_to_server_token.return_value = mock_token

        yield mock_instance


@pytest.fixture
def mock_github_repo_client():
    """Mock GitHubRepoClient for testing."""
    with patch("spec_compiler.app.routes.compile.GitHubRepoClient") as mock_class:
        mock_instance = MagicMock()
        mock_class.return_value = mock_instance

        # Default behavior: successful file fetching
        mock_instance.get_json_file.side_effect = lambda owner, repo, path, token: {
            "tree.json": {"tree": [{"path": "src/main.py", "type": "blob"}]},
            "dependencies.json": {"dependencies": [{"name": "fastapi", "version": "0.100.0"}]},
            "file-summaries.json": {"summaries": [{"path": "src/main.py", "summary": "Main entry point"}]},
        }.get(path.split("/")[-1], {})

        yield mock_instance


def test_compile_with_successful_repo_context_fetch(
    test_client: TestClient,
    mock_github_auth_client,
    mock_github_repo_client,
) -> None:
    """Test compile endpoint with successful repo context fetching."""
    payload = {
        "plan_id": "plan-repo-context",
        "spec_index": 0,
        "spec_data": {"type": "feature"},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "accepted"
    assert data["plan_id"] == "plan-repo-context"

    # Verify token minting was called
    mock_github_auth_client.mint_user_to_server_token.assert_called_once_with(
        owner="test-owner",
        repo="test-repo",
    )

    # Verify file fetching was attempted (3 files)
    assert mock_github_repo_client.get_json_file.call_count == 3


def test_compile_with_minting_error_returns_5xx(
    test_client: TestClient,
    mock_github_auth_client,
) -> None:
    """Test that minting errors result in 5xx responses."""
    # Simulate minting service failure
    mock_github_auth_client.mint_user_to_server_token.side_effect = MintingError(
        "Minting service returned status 500",
        status_code=500,
    )

    payload = {
        "plan_id": "plan-minting-error",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    # Should return 503 Service Unavailable for 5xx minting errors
    assert response.status_code == 503
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], dict)
    assert "error" in data["detail"]
    assert "request_id" in data["detail"]
    assert "plan_id" in data["detail"]
    assert data["detail"]["plan_id"] == "plan-minting-error"


def test_compile_with_minting_error_4xx_returns_502(
    test_client: TestClient,
    mock_github_auth_client,
) -> None:
    """Test that 4xx minting errors result in 502 Bad Gateway."""
    mock_github_auth_client.mint_user_to_server_token.side_effect = MintingError(
        "Minting service returned status 404",
        status_code=404,
    )

    payload = {
        "plan_id": "plan-minting-404",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 502
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], dict)


def test_compile_with_minting_not_configured_returns_500(
    test_client: TestClient,
    mock_github_auth_client,
) -> None:
    """Test that configuration errors result in 500 Internal Server Error."""
    mock_github_auth_client.mint_user_to_server_token.side_effect = MintingError(
        "Minting service URL not configured",
    )

    payload = {
        "plan_id": "plan-not-configured",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 500
    data = response.json()
    assert "detail" in data
    assert isinstance(data["detail"], dict)


def test_compile_with_missing_tree_json_uses_fallback(
    test_client: TestClient,
    mock_github_auth_client,
    mock_github_repo_client,
) -> None:
    """Test that missing tree.json uses fallback without failing request."""
    # Simulate tree.json not found
    def mock_get_json_file(owner, repo, path, token):
        if "tree.json" in path:
            raise GitHubFileError("Not found", status_code=404)
        return {
            "dependencies.json": {"dependencies": [{"name": "pytest", "version": "8.0.0"}]},
            "file-summaries.json": {"summaries": [{"path": "test.py", "summary": "Test file"}]},
        }.get(path.split("/")[-1], {})

    mock_github_repo_client.get_json_file.side_effect = mock_get_json_file

    payload = {
        "plan_id": "plan-missing-tree",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    # Request should still succeed with fallback
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_compile_with_all_files_missing_uses_all_fallbacks(
    test_client: TestClient,
    mock_github_auth_client,
    mock_github_repo_client,
) -> None:
    """Test that all missing files result in all fallbacks being used."""
    # Simulate all files not found
    mock_github_repo_client.get_json_file.side_effect = GitHubFileError(
        "Not found",
        status_code=404,
    )

    payload = {
        "plan_id": "plan-all-missing",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    # Request should still succeed with all fallbacks
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"

    # All 3 files should have been attempted
    assert mock_github_repo_client.get_json_file.call_count == 3


def test_compile_with_malformed_json_uses_fallback(
    test_client: TestClient,
    mock_github_auth_client,
    mock_github_repo_client,
) -> None:
    """Test that malformed JSON files use fallback without failing request."""
    # Simulate malformed dependencies.json
    def mock_get_json_file(owner, repo, path, token):
        if "dependencies.json" in path:
            raise InvalidJSONError("Failed to parse JSON content")
        return {
            "tree.json": {"tree": [{"path": "main.py", "type": "blob"}]},
            "file-summaries.json": {"summaries": []},
        }.get(path.split("/")[-1], {})

    mock_github_repo_client.get_json_file.side_effect = mock_get_json_file

    payload = {
        "plan_id": "plan-malformed-json",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    # Request should still succeed with fallback for malformed file
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_compile_with_partial_file_success(
    test_client: TestClient,
    mock_github_auth_client,
    mock_github_repo_client,
) -> None:
    """Test that partial success (some files missing) still completes request."""
    # Simulate tree.json success, but dependencies.json fails
    def mock_get_json_file(owner, repo, path, token):
        if "tree.json" in path:
            return {"tree": [{"path": "src/app.py", "type": "blob"}]}
        elif "dependencies.json" in path:
            raise GitHubFileError("Rate limit exceeded", status_code=403)
        elif "file-summaries.json" in path:
            return {"summaries": [{"path": "src/app.py", "summary": "Application entry"}]}
        return {}

    mock_github_repo_client.get_json_file.side_effect = mock_get_json_file

    payload = {
        "plan_id": "plan-partial-success",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    # Request should succeed with mixed results
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_compile_repo_context_fetch_unexpected_error(
    test_client: TestClient,
    mock_github_auth_client,
    mock_github_repo_client,
) -> None:
    """Test that unexpected errors during repo context fetch use fallbacks."""
    # Simulate unexpected error
    mock_github_repo_client.get_json_file.side_effect = RuntimeError("Unexpected error")

    payload = {
        "plan_id": "plan-unexpected-error",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    # Request should still succeed using fallback
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_compile_error_response_maintains_valid_json(
    test_client: TestClient,
    mock_github_auth_client,
) -> None:
    """Test that error responses contain valid JSON without literal 'failed' status."""
    mock_github_auth_client.mint_user_to_server_token.side_effect = MintingError(
        "Service unavailable",
        status_code=503,
    )

    payload = {
        "plan_id": "plan-json-check",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    # Verify response is valid JSON
    assert response.status_code == 503
    data = response.json()

    # Verify structure is valid and doesn't have status="failed" string literal
    assert isinstance(data, dict)
    assert "detail" in data
    assert isinstance(data["detail"], dict)
    # The actual CompileResponse isn't returned for 5xx errors,
    # so we don't expect a "status" field at the top level


def test_compile_logs_repo_context_metadata(
    test_client: TestClient,
    mock_github_auth_client,
    mock_github_repo_client,
    caplog,
) -> None:
    """Test that repo context metadata is logged."""
    import logging
    caplog.set_level(logging.INFO)

    payload = {
        "plan_id": "plan-logging-check",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202

    # Check for logging of minting and repo context
    log_messages = [record.message for record in caplog.records]
    assert any("minting_token_start" in msg for msg in log_messages)
    assert any("minting_token_success" in msg for msg in log_messages)
    assert any("fetching_repo_context_start" in msg for msg in log_messages)
    assert any("fetching_repo_context_success" in msg for msg in log_messages)


def test_compile_with_non_list_tree_data_uses_fallback(
    test_client: TestClient,
    mock_github_auth_client,
    mock_github_repo_client,
) -> None:
    """Test that non-list tree data triggers fallback."""
    # Simulate tree.json returning a dict instead of list inside "tree" key
    def mock_get_json_file(owner, repo, path, token):
        if "tree.json" in path:
            return {"tree": {"invalid": "not a list"}}  # Invalid: should be list
        return {
            "dependencies.json": {"dependencies": []},
            "file-summaries.json": {"summaries": []},
        }.get(path.split("/")[-1], {})

    mock_github_repo_client.get_json_file.side_effect = mock_get_json_file

    payload = {
        "plan_id": "plan-invalid-tree-type",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    # Request should succeed with fallback
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_fetch_repo_context_function_directly():
    """Test the fetch_repo_context helper function directly."""
    from spec_compiler.app.routes.compile import fetch_repo_context

    with patch("spec_compiler.app.routes.compile.GitHubRepoClient") as mock_client_class:
        mock_instance = MagicMock()
        mock_client_class.return_value = mock_instance

        # Mock successful file fetches
        mock_instance.get_json_file.side_effect = lambda owner, repo, path, token: {
            ".github/repo-analysis-output/tree.json": {"tree": [{"path": "main.py"}]},
            ".github/repo-analysis-output/dependencies.json": {"dependencies": [{"name": "fastapi"}]},
            ".github/repo-analysis-output/file-summaries.json": {"summaries": [{"path": "main.py", "summary": "Main"}]},
        }.get(path, {})

        result = fetch_repo_context(
            owner="test-owner",
            repo="test-repo",
            token="gho_test",
            request_id="test-request-id",
        )

        assert len(result.tree) == 1
        assert len(result.dependencies) == 1
        assert len(result.file_summaries) == 1
        assert result.tree[0]["path"] == "main.py"
        assert result.dependencies[0]["name"] == "fastapi"
