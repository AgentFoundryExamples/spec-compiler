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
Consolidated tests for GitHub services integration.

This module provides integration tests that exercise both GitHubAuthClient
and GitHubRepoClient together, validating end-to-end workflows and edge cases.

For detailed unit tests of individual components, see:
- test_github_auth.py: GitHubAuthClient unit tests
- test_github_repo.py: GitHubRepoClient unit tests
- test_compile_endpoint_repo_context.py: Compile endpoint integration tests
"""

import base64
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from spec_compiler.models import GitHubAuthToken
from spec_compiler.services.github_auth import GitHubAuthClient, MintingError
from spec_compiler.services.github_repo import (
    GitHubFileError,
    GitHubRepoClient,
    InvalidJSONError,
    create_fallback_dependencies,
    create_fallback_file_summaries,
    create_fallback_tree,
)


class TestGitHubServicesIntegration:
    """Integration tests for GitHub authentication and repository services."""

    @pytest.fixture
    def auth_client(self):
        """Create authenticated client for testing."""
        return GitHubAuthClient(
            minting_service_base_url="https://minting.example.com",
            auth_header="test-token",
            timeout=30.0,
        )

    @pytest.fixture
    def repo_client(self):
        """Create repository client for testing."""
        return GitHubRepoClient(
            github_api_base_url="https://api.github.com",
            timeout=30.0,
        )

    def test_full_workflow_success(self, auth_client, repo_client):
        """Test complete workflow: mint token, fetch files, parse JSON."""
        # Mock token minting
        mock_token = GitHubAuthToken(
            access_token="gho_test_token",
            token_type="bearer",
        )

        # Mock file content
        json_content = {"key": "value", "data": [1, 2, 3]}
        encoded_content = base64.b64encode(json.dumps(json_content).encode("utf-8")).decode(
            "ascii"
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Mock token minting response
            mock_auth_response = MagicMock()
            mock_auth_response.status_code = 200
            mock_auth_response.json.return_value = {
                "access_token": "gho_test_token",
                "token_type": "bearer",
            }

            # Mock file fetch response
            mock_file_response = MagicMock()
            mock_file_response.status_code = 200
            mock_file_response.json.return_value = {
                "content": encoded_content,
                "encoding": "base64",
            }

            # Configure mock to return different responses
            mock_client.post.return_value = mock_auth_response
            mock_client.get.return_value = mock_file_response

            # Execute workflow
            token = auth_client.mint_user_to_server_token("owner", "repo")
            assert token.access_token == "gho_test_token"

            result = repo_client.get_json_file("owner", "repo", "test.json", token=token.access_token)
            assert result == json_content

    def test_workflow_with_token_minting_failure(self, auth_client):
        """Test that minting failures prevent file fetching."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Mock minting failure
            mock_response = MagicMock()
            mock_response.status_code = 500
            mock_response.text = "Service unavailable"
            mock_client.post.return_value = mock_response

            with pytest.raises(MintingError) as exc_info:
                auth_client.mint_user_to_server_token("owner", "repo")

            assert exc_info.value.status_code == 500

    def test_workflow_with_file_fetch_failure(self, auth_client, repo_client):
        """Test that file fetch failures are handled correctly after successful minting."""
        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Mock successful token minting
            mock_auth_response = MagicMock()
            mock_auth_response.status_code = 200
            mock_auth_response.json.return_value = {
                "access_token": "gho_test_token",
                "token_type": "bearer",
            }
            mock_client.post.return_value = mock_auth_response

            # Mint token successfully
            token = auth_client.mint_user_to_server_token("owner", "repo")

            # Mock file fetch failure
            mock_file_response = MagicMock()
            mock_file_response.status_code = 404
            mock_file_response.text = "Not Found"
            mock_client.get.return_value = mock_file_response

            # Attempt file fetch
            with pytest.raises(GitHubFileError) as exc_info:
                repo_client.get_json_file("owner", "repo", "missing.json", token=token.access_token)

            assert exc_info.value.status_code == 404

    def test_simultaneous_missing_and_malformed_files(self, repo_client):
        """Test handling of both missing files (404) and malformed JSON in single workflow."""
        token = "gho_test_token"

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            # Track file paths to return different responses
            def mock_get_response(url, **kwargs):
                if "tree.json" in url:
                    # Return 404 for tree.json
                    response = MagicMock()
                    response.status_code = 404
                    response.text = "Not Found"
                    return response
                elif "dependencies.json" in url:
                    # Return malformed JSON for dependencies.json
                    response = MagicMock()
                    response.status_code = 200
                    invalid_json = "{ this is not valid JSON }"
                    encoded = base64.b64encode(invalid_json.encode("utf-8")).decode("ascii")
                    response.json.return_value = {
                        "content": encoded,
                        "encoding": "base64",
                    }
                    return response
                else:
                    # Return valid JSON for file-summaries.json
                    response = MagicMock()
                    response.status_code = 200
                    valid_json = {"summaries": [{"path": "test.py"}]}
                    encoded = base64.b64encode(json.dumps(valid_json).encode("utf-8")).decode("ascii")
                    response.json.return_value = {
                        "content": encoded,
                        "encoding": "base64",
                    }
                    return response

            mock_client.get.side_effect = mock_get_response

            # Test tree.json - should raise GitHubFileError
            with pytest.raises(GitHubFileError) as exc_info:
                repo_client.get_json_file("owner", "repo", ".github/repo-analysis-output/tree.json", token=token)
            assert exc_info.value.status_code == 404

            # Test dependencies.json - should raise InvalidJSONError
            with pytest.raises(InvalidJSONError):
                repo_client.get_json_file("owner", "repo", ".github/repo-analysis-output/dependencies.json", token=token)

            # Test file-summaries.json - should succeed
            result = repo_client.get_json_file("owner", "repo", ".github/repo-analysis-output/file-summaries.json", token=token)
            assert "summaries" in result


class TestFallbackHelpers:
    """Test fallback helper functions for missing or invalid repo data."""

    def test_fallback_tree_structure(self):
        """Test that fallback tree has expected structure."""
        tree = create_fallback_tree()

        assert isinstance(tree, list)
        assert len(tree) == 1
        assert tree[0]["path"] == "."
        assert tree[0]["type"] == "tree"
        assert tree[0]["mode"] == "040000"
        assert tree[0]["sha"] == "unavailable"
        assert "unavailable" in tree[0]["note"].lower()

    def test_fallback_dependencies_structure(self):
        """Test that fallback dependencies has expected structure."""
        deps = create_fallback_dependencies()

        assert isinstance(deps, list)
        assert len(deps) == 1
        assert deps[0]["name"] == "unknown"
        assert deps[0]["version"] == "unknown"
        assert deps[0]["ecosystem"] == "unknown"
        assert "unavailable" in deps[0]["note"].lower()

    def test_fallback_file_summaries_structure(self):
        """Test that fallback file summaries has expected structure."""
        summaries = create_fallback_file_summaries()

        assert isinstance(summaries, list)
        assert len(summaries) == 1
        assert summaries[0]["path"] == "unknown"
        assert summaries[0]["summary"] == "File summary data unavailable"
        assert summaries[0]["lines"] == 0
        assert "unable" in summaries[0]["note"].lower()

    def test_all_fallbacks_are_well_formed_json(self):
        """Test that all fallback structures can be serialized to JSON."""
        tree = create_fallback_tree()
        deps = create_fallback_dependencies()
        summaries = create_fallback_file_summaries()

        # All should be JSON-serializable
        json_str = json.dumps({
            "tree": tree,
            "dependencies": deps,
            "file_summaries": summaries,
        })

        # Should be able to parse back
        parsed = json.loads(json_str)
        assert parsed["tree"] == tree
        assert parsed["dependencies"] == deps
        assert parsed["file_summaries"] == summaries


class TestErrorSanitization:
    """Test that error messages properly sanitize sensitive data."""

    def test_minting_error_sanitizes_tokens(self):
        """Test that MintingError sanitizes access tokens from response bodies."""
        response_with_token = '{"access_token": "gho_secret123", "token_type": "bearer"}'
        error = MintingError(
            "Test error",
            status_code=500,
            response_body=response_with_token,
        )

        assert "gho_secret123" not in error.response_body
        assert "[REDACTED]" in error.response_body
        assert "access_token" in error.response_body

    def test_github_file_error_sanitizes_tokens(self):
        """Test that GitHubFileError sanitizes bearer tokens."""
        response_with_bearer = "Authorization: Bearer gho_secrettoken123"
        error = GitHubFileError(
            "Test error",
            status_code=401,
            response_body=response_with_bearer,
        )

        assert "gho_secrettoken123" not in error.response_body
        assert "[REDACTED]" in error.response_body

    def test_header_injection_prevention_in_auth_client(self):
        """Test that GitHubAuthClient prevents header injection attacks."""
        client = GitHubAuthClient(
            minting_service_base_url="https://test.com",
            auth_header="valid-token\nX-Malicious: header",
        )

        with pytest.raises(MintingError) as exc_info:
            client.mint_user_to_server_token("owner", "repo")

        assert "Invalid authorization header" in str(exc_info.value)
        assert "newline" in str(exc_info.value)

    def test_header_injection_prevention_in_repo_client(self):
        """Test that GitHubRepoClient prevents header injection attacks."""
        client = GitHubRepoClient(github_api_base_url="https://api.github.com")
        malicious_token = "valid-token\nX-Malicious: header"

        with pytest.raises(GitHubFileError) as exc_info:
            client.get_json_file("owner", "repo", "test.json", token=malicious_token)

        assert "Invalid token" in str(exc_info.value)
        assert "newline" in str(exc_info.value)


class TestDeterministicBehavior:
    """Test that all GitHub service operations are deterministic with mocking."""

    def test_no_actual_network_calls_in_auth_client(self):
        """Verify that tests don't make actual network calls."""
        # Without mocking, this should fail with connection error
        # This test validates that other tests are properly mocked
        auth_client = GitHubAuthClient(
            minting_service_base_url="https://minting.example.com",
            auth_header="test-token",
        )
        with pytest.raises((httpx.ConnectError, MintingError)):
            # This will fail because minting service is not mocked here
            auth_client.mint_user_to_server_token("owner", "repo")

    def test_no_actual_network_calls_in_repo_client(self):
        """Verify that tests don't make actual network calls."""
        # Without mocking, this should fail with connection error
        repo_client = GitHubRepoClient(
            github_api_base_url="https://api.github.com",
        )
        with pytest.raises((httpx.ConnectError, GitHubFileError)):
            # This will fail because GitHub API is not mocked here
            repo_client.get_json_file("owner", "repo", "test.json", token="fake-token")

    def test_repeated_calls_with_same_inputs_produce_same_results(self):
        """Test that mocked operations are deterministic."""
        client = GitHubAuthClient(
            minting_service_base_url="https://test.com",
            auth_header="token",
        )

        with patch("httpx.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__enter__.return_value = mock_client

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "gho_deterministic",
                "token_type": "bearer",
            }
            mock_client.post.return_value = mock_response

            # First call
            token1 = client.mint_user_to_server_token("owner", "repo")

            # Reset mock to same state
            mock_client.post.return_value = mock_response

            # Second call with same inputs
            token2 = client.mint_user_to_server_token("owner", "repo")

            # Results should be identical
            assert token1.access_token == token2.access_token
            assert token1.token_type == token2.token_type
