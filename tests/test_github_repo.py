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
Tests for GitHub repository client.

Validates GitHubRepoClient behavior including file fetching,
base64 decoding, JSON parsing, error handling, and fallback helpers.
"""

import base64
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest

from spec_compiler.services.github_repo import (
    GitHubFileError,
    GitHubRepoClient,
    InvalidJSONError,
    create_fallback_dependencies,
    create_fallback_file_summaries,
    create_fallback_tree,
)


@pytest.fixture
def mock_settings():
    """Mock settings for tests."""
    with patch("spec_compiler.services.github_repo.settings") as mock:
        mock.github_api_base_url = "https://api.github.com"
        yield mock


@pytest.fixture
def repo_client(mock_settings):
    """Create a repo client for testing."""
    return GitHubRepoClient(
        github_api_base_url="https://api.github.com",
        timeout=30.0,
    )


def test_github_repo_client_initialization():
    """Test that GitHubRepoClient initializes with correct defaults."""
    client = GitHubRepoClient(
        github_api_base_url="https://test.com",
        timeout=15.0,
    )

    assert client.github_api_base_url == "https://test.com"
    assert client.timeout == 15.0


def test_get_json_file_success(repo_client):
    """Test successful JSON file retrieval with base64 encoding."""
    json_content = {"key": "value", "nested": {"data": [1, 2, 3]}}
    encoded_content = base64.b64encode(json.dumps(json_content).encode("utf-8")).decode("ascii")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": encoded_content,
        "encoding": "base64",
        "name": "test.json",
        "path": "path/to/test.json",
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        result = repo_client.get_json_file("owner", "repo", "path/to/test.json")

        assert result == json_content
        assert result["key"] == "value"
        assert result["nested"]["data"] == [1, 2, 3]

        # Verify HTTP request
        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert (
            "https://api.github.com/repos/owner/repo/contents/path/to/test.json" in call_args[0][0]
        )
        assert "Accept" in call_args[1]["headers"]
        assert "Authorization" not in call_args[1]["headers"]  # No token provided


def test_get_json_file_with_token(repo_client):
    """Test JSON file retrieval with authentication token."""
    json_content = {"authenticated": True}
    encoded_content = base64.b64encode(json.dumps(json_content).encode("utf-8")).decode("ascii")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": encoded_content,
        "encoding": "base64",
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        result = repo_client.get_json_file("owner", "repo", "test.json", token="gho_token123")

        assert result == json_content

        # Verify Authorization header
        call_args = mock_client.get.call_args
        assert call_args[1]["headers"]["Authorization"] == "Bearer gho_token123"


def test_get_json_file_with_newlines_in_base64(repo_client):
    """Test that base64 content with newlines is decoded correctly."""
    json_content = {"data": "test"}
    encoded_content = base64.b64encode(json.dumps(json_content).encode("utf-8")).decode("ascii")
    # Add newlines to simulate GitHub's response format
    encoded_with_newlines = "\n".join(
        [encoded_content[i : i + 60] for i in range(0, len(encoded_content), 60)]
    )

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": encoded_with_newlines,
        "encoding": "base64",
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        result = repo_client.get_json_file("owner", "repo", "test.json")

        assert result == json_content


def test_get_json_file_plaintext_encoding(repo_client):
    """Test handling of plain text content (no base64 encoding)."""
    json_content = {"plain": "text"}
    plain_content = json.dumps(json_content)

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": plain_content,
        "encoding": None,
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        result = repo_client.get_json_file("owner", "repo", "test.json")

        assert result == json_content


def test_get_json_file_404_error(repo_client):
    """Test handling of 404 Not Found error."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not Found"

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        with pytest.raises(GitHubFileError) as exc_info:
            repo_client.get_json_file("owner", "repo", "missing.json")

        assert "status 404" in str(exc_info.value)
        assert exc_info.value.status_code == 404
        assert exc_info.value.context["owner"] == "owner"
        assert exc_info.value.context["repo"] == "repo"
        assert exc_info.value.context["path"] == "missing.json"


def test_get_json_file_500_error(repo_client):
    """Test handling of 500 Internal Server Error."""
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        with pytest.raises(GitHubFileError) as exc_info:
            repo_client.get_json_file("owner", "repo", "test.json")

        assert "status 500" in str(exc_info.value)
        assert exc_info.value.status_code == 500


def test_get_json_file_invalid_response_json(repo_client):
    """Test handling of invalid JSON in GitHub API response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.text = "Not valid JSON"

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        with pytest.raises(GitHubFileError) as exc_info:
            repo_client.get_json_file("owner", "repo", "test.json")

        assert "Failed to parse GitHub API response" in str(exc_info.value)
        assert "parse_error" in exc_info.value.context


def test_get_json_file_missing_content_field(repo_client):
    """Test handling of missing 'content' field in response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "encoding": "base64",
        # Missing 'content' field
    }
    mock_response.text = '{"encoding": "base64"}'

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        with pytest.raises(GitHubFileError) as exc_info:
            repo_client.get_json_file("owner", "repo", "test.json")

        assert "missing 'content' field" in str(exc_info.value)
        assert "missing_field" in exc_info.value.context


def test_get_json_file_base64_decode_error(repo_client):
    """Test handling of base64 decode errors."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": "not-valid-base64!!!",
        "encoding": "base64",
    }
    mock_response.text = '{"content": "not-valid-base64!!!", "encoding": "base64"}'

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        with pytest.raises(GitHubFileError) as exc_info:
            repo_client.get_json_file("owner", "repo", "test.json")

        assert "Failed to decode base64" in str(exc_info.value)
        assert "decode_error" in exc_info.value.context


def test_get_json_file_unexpected_encoding(repo_client):
    """Test handling of unexpected encoding format."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": "some content",
        "encoding": "gzip",  # Unexpected encoding
    }
    mock_response.text = '{"content": "some content", "encoding": "gzip"}'

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        with pytest.raises(GitHubFileError) as exc_info:
            repo_client.get_json_file("owner", "repo", "test.json")

        assert "Unexpected encoding format" in str(exc_info.value)
        assert exc_info.value.context["encoding"] == "gzip"


def test_get_json_file_invalid_json_content(repo_client):
    """Test handling of invalid JSON content in file."""
    invalid_json = "{ this is not valid JSON }"
    encoded_content = base64.b64encode(invalid_json.encode("utf-8")).decode("ascii")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": encoded_content,
        "encoding": "base64",
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        with pytest.raises(InvalidJSONError) as exc_info:
            repo_client.get_json_file("owner", "repo", "test.json")

        assert "Failed to parse JSON content" in str(exc_info.value)
        assert exc_info.value.content == invalid_json
        assert "json_error" in exc_info.value.context


def test_get_json_file_non_dict_json(repo_client):
    """Test that non-dict JSON raises InvalidJSONError."""
    json_array = [1, 2, 3]  # Array, not dict
    encoded_content = base64.b64encode(json.dumps(json_array).encode("utf-8")).decode("ascii")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": encoded_content,
        "encoding": "base64",
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        with pytest.raises(InvalidJSONError) as exc_info:
            repo_client.get_json_file("owner", "repo", "test.json")

        assert "Expected JSON object (dict), got list" in str(exc_info.value)
        assert exc_info.value.context["actual_type"] == "list"


def test_get_json_file_http_exception(repo_client):
    """Test handling of HTTP exceptions."""
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = httpx.ConnectError("Connection failed")

        with pytest.raises(GitHubFileError) as exc_info:
            repo_client.get_json_file("owner", "repo", "test.json")

        assert "HTTP error" in str(exc_info.value)
        assert "exception" in exc_info.value.context


def test_get_json_file_unexpected_exception(repo_client):
    """Test handling of unexpected exceptions."""
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.side_effect = RuntimeError("Unexpected error")

        with pytest.raises(GitHubFileError) as exc_info:
            repo_client.get_json_file("owner", "repo", "test.json")

        assert "Unexpected error" in str(exc_info.value)
        assert "exception" in exc_info.value.context


def test_create_fallback_tree():
    """Test fallback tree creation."""
    tree = create_fallback_tree()

    assert isinstance(tree, list)
    assert len(tree) == 1
    assert tree[0]["path"] == "."
    assert tree[0]["type"] == "tree"
    assert "unavailable" in tree[0]["note"].lower()


def test_create_fallback_dependencies():
    """Test fallback dependencies creation."""
    deps = create_fallback_dependencies()

    assert isinstance(deps, list)
    assert len(deps) == 1
    assert deps[0]["name"] == "unknown"
    assert deps[0]["version"] == "unknown"
    assert "unavailable" in deps[0]["note"].lower()


def test_create_fallback_file_summaries():
    """Test fallback file summaries creation."""
    summaries = create_fallback_file_summaries()

    assert isinstance(summaries, list)
    assert len(summaries) == 1
    assert summaries[0]["path"] == "unknown"
    assert summaries[0]["lines"] == 0
    assert "unavailable" in summaries[0]["summary"].lower()


def test_get_json_file_url_formatting(repo_client):
    """Test that URLs are formatted correctly with trailing slashes."""
    json_content = {"test": "data"}
    encoded_content = base64.b64encode(json.dumps(json_content).encode("utf-8")).decode("ascii")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": encoded_content,
        "encoding": "base64",
    }

    # Test with base URL that has trailing slash
    client_with_slash = GitHubRepoClient(github_api_base_url="https://api.github.com/")

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        client_with_slash.get_json_file("owner", "repo", "test.json")

        # Verify URL doesn't have double slashes
        call_args = mock_client.get.call_args
        url = call_args[0][0]
        assert url == "https://api.github.com/repos/owner/repo/contents/test.json"
        assert "//" not in url.replace("https://", "")


def test_get_json_file_header_injection_prevention(repo_client):
    """Test that header injection is prevented in tokens."""
    malicious_token = "valid-token\nX-Malicious: header"

    with pytest.raises(GitHubFileError) as exc_info:
        repo_client.get_json_file("owner", "repo", "test.json", token=malicious_token)

    assert "Invalid token" in str(exc_info.value)
    assert "newline" in str(exc_info.value)


def test_github_file_error_sanitizes_response_body():
    """Test that GitHubFileError sanitizes sensitive data from response body."""
    response_with_token = "Authorization: Bearer gho_secret123"
    error = GitHubFileError(
        "Test error",
        status_code=401,
        response_body=response_with_token,
    )

    assert "gho_secret123" not in error.response_body
    assert "[REDACTED]" in error.response_body


def test_get_json_file_plaintext_null_content(repo_client):
    """Test handling of null content with plaintext encoding."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": None,
        "encoding": None,
    }
    mock_response.text = '{"content": null, "encoding": null}'

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        with pytest.raises(GitHubFileError) as exc_info:
            repo_client.get_json_file("owner", "repo", "test.json")

        assert "content is null" in str(exc_info.value)


def test_get_json_file_plaintext_non_string_content(repo_client):
    """Test handling of non-string content with plaintext encoding."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "content": 12345,  # Not a string
        "encoding": None,
    }
    mock_response.text = '{"content": 12345, "encoding": null}'

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_response

        with pytest.raises(GitHubFileError) as exc_info:
            repo_client.get_json_file("owner", "repo", "test.json")

        assert "not a string" in str(exc_info.value)
        assert "int" in str(exc_info.value)
