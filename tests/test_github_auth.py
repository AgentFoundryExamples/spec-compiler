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
Tests for GitHub authentication client.

Validates GitHubAuthClient behavior including token minting,
error handling, caching, and edge cases.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import httpx
import pytest

from spec_compiler.models import GitHubAuthToken
from spec_compiler.services.github_auth import GitHubAuthClient, MintingError


@pytest.fixture
def mock_settings():
    """Mock settings for tests."""
    with patch("spec_compiler.services.github_auth.settings") as mock:
        mock.minting_service_base_url = "https://minting.example.com"
        mock.minting_service_auth_header = "test-token"
        mock.github_api_base_url = "https://api.github.com"
        yield mock


@pytest.fixture
def auth_client(mock_settings):
    """Create an authenticated client for testing."""
    return GitHubAuthClient(
        minting_service_base_url="https://minting.example.com",
        auth_header="test-token",
        timeout=30.0,
        enable_caching=True,
        cache_expiry_buffer_seconds=300,
    )


@pytest.fixture
def auth_client_no_cache(mock_settings):
    """Create an authenticated client without caching."""
    return GitHubAuthClient(
        minting_service_base_url="https://minting.example.com",
        auth_header="test-token",
        timeout=30.0,
        enable_caching=False,
        cache_expiry_buffer_seconds=300,
    )


def test_github_auth_client_initialization():
    """Test that GitHubAuthClient initializes with correct defaults."""
    client = GitHubAuthClient(
        minting_service_base_url="https://test.com",
        auth_header="token",
    )

    assert client.minting_service_base_url == "https://test.com"
    assert client.auth_header == "token"
    assert client.timeout == 30.0
    assert client.enable_caching is True
    assert client._token_cache == {}


def test_mint_user_to_server_token_success(auth_client):
    """Test successful token minting."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "gho_test123",
        "token_type": "bearer",
        "expires_at": "2025-12-31T23:59:59+00:00",
        "scope": "repo,user",
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        token = auth_client.mint_user_to_server_token("owner", "repo")

        assert isinstance(token, GitHubAuthToken)
        assert token.access_token == "gho_test123"
        assert token.token_type == "bearer"
        assert token.expires_at == "2025-12-31T23:59:59+00:00"
        assert token.scope == "repo,user"

        # Verify HTTP request
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://minting.example.com/api/token"
        assert "Authorization" in call_args[1]["headers"]
        assert call_args[1]["json"]["force_refresh"] is False


def test_mint_user_to_server_token_non_expiring(auth_client):
    """Test minting token without expiry."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "gho_test456",
        "token_type": "bearer",
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        token = auth_client.mint_user_to_server_token("owner", "repo")

        assert token.access_token == "gho_test456"
        assert token.expires_at is None
        assert token.scope is None


def test_mint_user_to_server_token_force_refresh(auth_client):
    """Test token minting with force_refresh=True."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "gho_refreshed",
        "token_type": "bearer",
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        token = auth_client.mint_user_to_server_token("owner", "repo", force_refresh=True)

        assert token.access_token == "gho_refreshed"

        # Verify force_refresh in request
        call_args = mock_client.post.call_args
        assert call_args[1]["json"]["force_refresh"] is True


def test_mint_user_to_server_token_caching(auth_client):
    """Test that tokens are cached and reused."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "gho_cached",
        "token_type": "bearer",
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        # First call - should hit API
        token1 = auth_client.mint_user_to_server_token("owner", "repo")
        assert mock_client.post.call_count == 1

        # Second call - should use cache
        token2 = auth_client.mint_user_to_server_token("owner", "repo")
        assert mock_client.post.call_count == 1  # No additional calls
        assert token1.access_token == token2.access_token


def test_mint_user_to_server_token_no_cache(auth_client_no_cache):
    """Test that caching can be disabled."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "gho_nocache",
        "token_type": "bearer",
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        # First call
        auth_client_no_cache.mint_user_to_server_token("owner", "repo")
        assert mock_client.post.call_count == 1

        # Second call - should hit API again (no caching)
        auth_client_no_cache.mint_user_to_server_token("owner", "repo")
        assert mock_client.post.call_count == 2


def test_mint_user_to_server_token_expired_cache(auth_client):
    """Test that expired cached tokens are invalidated."""
    # Create an expired token in cache
    expiry = (datetime.now(UTC) - timedelta(minutes=10)).isoformat()
    expired_token = GitHubAuthToken(
        access_token="gho_expired",
        token_type="bearer",
        expires_at=expiry,
    )
    auth_client._token_cache["owner/repo"] = expired_token

    # Mock fresh token response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "gho_fresh",
        "token_type": "bearer",
    }

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        token = auth_client.mint_user_to_server_token("owner", "repo")

        # Should fetch new token, not use expired cache
        assert token.access_token == "gho_fresh"
        assert mock_client.post.call_count == 1


def test_mint_user_to_server_token_missing_url():
    """Test error when minting service URL is not configured."""
    client = GitHubAuthClient(
        minting_service_base_url=None,
        auth_header="token",
    )

    with pytest.raises(MintingError) as exc_info:
        client.mint_user_to_server_token("owner", "repo")

    assert "Minting service URL not configured" in str(exc_info.value)
    assert exc_info.value.context["owner"] == "owner"
    assert exc_info.value.context["repo"] == "repo"


def test_mint_user_to_server_token_http_error(auth_client):
    """Test error handling for HTTP errors."""
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.text = "Not found"

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        with pytest.raises(MintingError) as exc_info:
            auth_client.mint_user_to_server_token("owner", "repo")

        assert "status 404" in str(exc_info.value)
        assert exc_info.value.status_code == 404
        assert exc_info.value.response_body == "Not found"


def test_mint_user_to_server_token_invalid_json(auth_client):
    """Test error handling for invalid JSON response."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.side_effect = ValueError("Invalid JSON")
    mock_response.text = "Not valid JSON"

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        with pytest.raises(MintingError) as exc_info:
            auth_client.mint_user_to_server_token("owner", "repo")

        assert "Failed to parse JSON" in str(exc_info.value)
        assert "parse_error" in exc_info.value.context


def test_mint_user_to_server_token_missing_access_token(auth_client):
    """Test error when response is missing access_token field."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "token_type": "bearer",
        # Missing access_token
    }
    mock_response.text = '{"token_type": "bearer"}'

    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.post.return_value = mock_response

        with pytest.raises(MintingError) as exc_info:
            auth_client.mint_user_to_server_token("owner", "repo")

        assert "missing 'access_token' field" in str(exc_info.value)
        assert "missing_field" in exc_info.value.context


def test_mint_user_to_server_token_http_exception(auth_client):
    """Test error handling for HTTP exceptions."""
    with patch("httpx.Client") as mock_client_class:
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_client.post.side_effect = httpx.ConnectError("Connection failed")

        with pytest.raises(MintingError) as exc_info:
            auth_client.mint_user_to_server_token("owner", "repo")

        assert "HTTP error" in str(exc_info.value)
        assert "exception" in exc_info.value.context


def test_is_token_valid_non_expiring(auth_client):
    """Test that non-expiring tokens are always valid."""
    token = GitHubAuthToken(
        access_token="gho_test",
        token_type="bearer",
        expires_at=None,
    )

    assert auth_client._is_token_valid(token) is True


def test_is_token_valid_future_expiry(auth_client):
    """Test that tokens expiring in the future are valid."""
    future_expiry = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    token = GitHubAuthToken(
        access_token="gho_test",
        token_type="bearer",
        expires_at=future_expiry,
    )

    assert auth_client._is_token_valid(token) is True


def test_is_token_valid_near_expiry(auth_client):
    """Test that tokens expiring soon are invalid."""
    near_expiry = (datetime.now(UTC) + timedelta(minutes=2)).isoformat()
    token = GitHubAuthToken(
        access_token="gho_test",
        token_type="bearer",
        expires_at=near_expiry,
    )

    # Should be invalid (< 5 minute buffer)
    assert auth_client._is_token_valid(token) is False


def test_is_token_valid_past_expiry(auth_client):
    """Test that expired tokens are invalid."""
    past_expiry = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    token = GitHubAuthToken(
        access_token="gho_test",
        token_type="bearer",
        expires_at=past_expiry,
    )

    assert auth_client._is_token_valid(token) is False


def test_is_token_valid_invalid_format(auth_client):
    """Test that tokens with invalid expiry format are invalid."""
    # Create a token with valid format but then manually corrupt it
    token = GitHubAuthToken(
        access_token="gho_test",
        token_type="bearer",
        expires_at="2025-12-31T23:59:59+00:00",
    )
    # Manually set invalid format to test error handling
    token.expires_at = "not-a-valid-timestamp"

    # Should be invalid due to parse error
    assert auth_client._is_token_valid(token) is False


def test_clear_cache_all(auth_client):
    """Test clearing entire cache."""
    auth_client._token_cache["owner1/repo1"] = MagicMock()
    auth_client._token_cache["owner2/repo2"] = MagicMock()

    auth_client.clear_cache()

    assert len(auth_client._token_cache) == 0


def test_clear_cache_specific_repo(auth_client):
    """Test clearing cache for specific repo."""
    auth_client._token_cache["owner1/repo1"] = MagicMock()
    auth_client._token_cache["owner1/repo2"] = MagicMock()
    auth_client._token_cache["owner2/repo1"] = MagicMock()

    auth_client.clear_cache("owner1", "repo1")

    assert "owner1/repo1" not in auth_client._token_cache
    assert "owner1/repo2" in auth_client._token_cache
    assert "owner2/repo1" in auth_client._token_cache


def test_clear_cache_owner(auth_client):
    """Test clearing cache for all repos of an owner."""
    auth_client._token_cache["owner1/repo1"] = MagicMock()
    auth_client._token_cache["owner1/repo2"] = MagicMock()
    auth_client._token_cache["owner2/repo1"] = MagicMock()

    auth_client.clear_cache("owner1")

    assert "owner1/repo1" not in auth_client._token_cache
    assert "owner1/repo2" not in auth_client._token_cache
    assert "owner2/repo1" in auth_client._token_cache


def test_mint_user_to_server_token_header_injection_prevention(auth_client):
    """Test that header injection is prevented."""
    # Create client with malicious auth header
    malicious_client = GitHubAuthClient(
        minting_service_base_url="https://minting.example.com",
        auth_header="valid-token\nX-Malicious: header",
    )

    with pytest.raises(MintingError) as exc_info:
        malicious_client.mint_user_to_server_token("owner", "repo")

    assert "Invalid authorization header" in str(exc_info.value)
    assert "newline" in str(exc_info.value)


def test_minting_error_sanitizes_response_body():
    """Test that MintingError sanitizes sensitive data from response body."""
    response_with_token = '{"access_token": "gho_secret123", "token_type": "bearer"}'
    error = MintingError(
        "Test error",
        status_code=500,
        response_body=response_with_token,
    )

    assert "gho_secret123" not in error.response_body
    assert "[REDACTED]" in error.response_body
    assert "access_token" in error.response_body


def test_minting_error_sanitizes_bearer_tokens():
    """Test that MintingError sanitizes bearer tokens in response."""
    response_with_bearer = "Authorization: Bearer gho_secrettoken123"
    error = MintingError(
        "Test error",
        response_body=response_with_bearer,
    )

    assert "gho_secrettoken123" not in error.response_body
    assert "[REDACTED]" in error.response_body


def test_cache_expiry_buffer_configurable():
    """Test that cache expiry buffer is configurable."""
    client = GitHubAuthClient(
        minting_service_base_url="https://test.com",
        auth_header="token",
        cache_expiry_buffer_seconds=600,  # 10 minutes
    )

    assert client.cache_expiry_buffer_seconds == 600

    # Test that it uses the configured buffer
    future_expiry = (datetime.now(UTC) + timedelta(minutes=8)).isoformat()
    token = GitHubAuthToken(
        access_token="gho_test",
        token_type="bearer",
        expires_at=future_expiry,
    )

    # With 10-minute buffer, 8 minutes should be invalid
    assert client._is_token_valid(token) is False


def test_clear_cache_owner_exact_match():
    """Test that clearing cache by owner uses exact match, not prefix."""
    client = GitHubAuthClient(
        minting_service_base_url="https://test.com",
        auth_header="token",
    )

    # Create tokens for owners that share a prefix
    client._token_cache["owner/repo1"] = MagicMock()
    client._token_cache["owner2/repo2"] = MagicMock()
    client._token_cache["owner-suffix/repo3"] = MagicMock()

    # Clear only 'owner' - should not match 'owner2' or 'owner-suffix'
    client.clear_cache("owner")

    assert "owner/repo1" not in client._token_cache
    assert "owner2/repo2" in client._token_cache
    assert "owner-suffix/repo3" in client._token_cache
