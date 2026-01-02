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
GitHub authentication client for token minting.

Provides GitHubAuthClient for minting GitHub user-to-server tokens
from the configured minting service endpoint.
"""

from datetime import UTC, datetime
from typing import Any

import httpx

from spec_compiler.config import settings
from spec_compiler.logging import get_logger
from spec_compiler.models import GitHubAuthToken

logger = get_logger(__name__)


class MintingError(Exception):
    """
    Exception raised when token minting fails.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code if applicable
        response_body: Raw response body for debugging
        context: Additional context about the error
    """

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body
        self.context = context or {}


class GitHubAuthClient:
    """
    Client for minting GitHub user-to-server access tokens.

    This client communicates with the GitHub token minting service
    to obtain access tokens for GitHub API operations. It handles
    HTTP errors, token parsing, and optional per-repo caching.
    """

    def __init__(
        self,
        minting_service_base_url: str | None = None,
        auth_header: str | None = None,
        timeout: float = 30.0,
        enable_caching: bool = True,
    ):
        """
        Initialize the GitHub authentication client.

        Args:
            minting_service_base_url: Base URL for minting service (defaults to config)
            auth_header: Authorization header value (defaults to config)
            timeout: HTTP request timeout in seconds
            enable_caching: Enable in-memory token caching per repo
        """
        self.minting_service_base_url = (
            minting_service_base_url or settings.minting_service_base_url
        )
        self.auth_header = auth_header or settings.minting_service_auth_header
        self.timeout = timeout
        self.enable_caching = enable_caching
        self._token_cache: dict[str, GitHubAuthToken] = {}

        if not self.minting_service_base_url:
            logger.warning(
                "minting_service_base_url_not_configured",
                message="Minting service URL not configured, token minting will fail",
            )

    def mint_user_to_server_token(
        self, owner: str, repo: str, force_refresh: bool = False
    ) -> GitHubAuthToken:
        """
        Mint a GitHub user-to-server access token for a specific repository.

        Args:
            owner: GitHub repository owner
            repo: GitHub repository name
            force_refresh: Force token refresh even if cached and valid

        Returns:
            GitHubAuthToken with access_token, token_type, expires_at, etc.

        Raises:
            MintingError: If minting fails due to HTTP errors, missing config,
                         or invalid response format
        """
        cache_key = f"{owner}/{repo}"

        # Check cache if enabled and not forcing refresh
        if self.enable_caching and not force_refresh and cache_key in self._token_cache:
            cached_token = self._token_cache[cache_key]
            if self._is_token_valid(cached_token):
                logger.info(
                    "token_cache_hit",
                    owner=owner,
                    repo=repo,
                    expires_at=cached_token.expires_at,
                )
                return cached_token
            else:
                logger.info(
                    "token_cache_expired",
                    owner=owner,
                    repo=repo,
                    expires_at=cached_token.expires_at,
                )
                # Remove expired token from cache
                del self._token_cache[cache_key]

        # Validate configuration
        if not self.minting_service_base_url:
            error_msg = "Minting service URL not configured"
            logger.error(
                "minting_error",
                error=error_msg,
                owner=owner,
                repo=repo,
            )
            raise MintingError(
                error_msg,
                context={
                    "owner": owner,
                    "repo": repo,
                    "config_missing": "minting_service_base_url",
                },
            )

        # Prepare request
        url = f"{self.minting_service_base_url.rstrip('/')}/api/token"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.auth_header:
            headers["Authorization"] = f"Bearer {self.auth_header}"

        request_body = {"force_refresh": force_refresh}

        logger.info(
            "minting_token_request",
            owner=owner,
            repo=repo,
            url=url,
            force_refresh=force_refresh,
        )

        try:
            # Make HTTP request to minting service
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, headers=headers, json=request_body)

            # Check for HTTP errors
            if response.status_code != 200:
                error_msg = f"Minting service returned status {response.status_code}"
                logger.error(
                    "minting_http_error",
                    owner=owner,
                    repo=repo,
                    status_code=response.status_code,
                    response_text=response.text[:500],  # Truncate for logging
                )
                raise MintingError(
                    error_msg,
                    status_code=response.status_code,
                    response_body=response.text,
                    context={"owner": owner, "repo": repo},
                )

            # Parse JSON response
            try:
                response_data = response.json()
            except Exception as e:
                error_msg = f"Failed to parse JSON response from minting service: {e}"
                logger.error(
                    "minting_json_parse_error",
                    owner=owner,
                    repo=repo,
                    error=str(e),
                    response_text=response.text[:500],
                )
                raise MintingError(
                    error_msg,
                    status_code=response.status_code,
                    response_body=response.text,
                    context={"owner": owner, "repo": repo, "parse_error": str(e)},
                ) from e

            # Validate required fields
            if "access_token" not in response_data:
                error_msg = "Minting service response missing 'access_token' field"
                logger.error(
                    "minting_missing_token_field",
                    owner=owner,
                    repo=repo,
                    response_keys=list(response_data.keys()),
                )
                raise MintingError(
                    error_msg,
                    status_code=response.status_code,
                    response_body=response.text,
                    context={
                        "owner": owner,
                        "repo": repo,
                        "missing_field": "access_token",
                        "response_keys": list(response_data.keys()),
                    },
                )

            # Create token model
            token = GitHubAuthToken(
                access_token=response_data["access_token"],
                token_type=response_data.get("token_type", "bearer"),
                expires_at=response_data.get("expires_at"),
                scope=response_data.get("scope"),
                created_at=datetime.now(UTC),
            )

            # Cache token if enabled
            if self.enable_caching:
                self._token_cache[cache_key] = token
                logger.info(
                    "token_cached",
                    owner=owner,
                    repo=repo,
                    expires_at=token.expires_at,
                )

            logger.info(
                "token_minted_success",
                owner=owner,
                repo=repo,
                token_type=token.token_type,
                expires_at=token.expires_at,
                has_expiry=token.expires_at is not None,
            )

            return token

        except httpx.HTTPError as e:
            error_msg = f"HTTP error during token minting: {e}"
            logger.error(
                "minting_http_exception",
                owner=owner,
                repo=repo,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MintingError(
                error_msg,
                context={"owner": owner, "repo": repo, "exception": str(e)},
            ) from e
        except MintingError:
            # Re-raise MintingError as-is
            raise
        except Exception as e:
            error_msg = f"Unexpected error during token minting: {e}"
            logger.error(
                "minting_unexpected_error",
                owner=owner,
                repo=repo,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise MintingError(
                error_msg,
                context={"owner": owner, "repo": repo, "exception": str(e)},
            ) from e

    def _is_token_valid(self, token: GitHubAuthToken) -> bool:
        """
        Check if a cached token is still valid.

        A token is valid if:
        - It has no expiry (expires_at is None), OR
        - Its expiry is more than 5 minutes in the future

        Args:
            token: Token to validate

        Returns:
            True if token is valid, False otherwise
        """
        if token.expires_at is None:
            # Token doesn't expire
            return True

        try:
            # Parse expiry timestamp
            expiry_dt = datetime.fromisoformat(token.expires_at.replace("Z", "+00:00"))
            now = datetime.now(UTC)

            # Check if token expires in more than 5 minutes
            time_until_expiry = (expiry_dt - now).total_seconds()
            return time_until_expiry > 300  # 5 minutes buffer

        except (ValueError, AttributeError) as e:
            logger.warning(
                "token_expiry_parse_error",
                expires_at=token.expires_at,
                error=str(e),
            )
            # If we can't parse expiry, consider token invalid
            return False

    def clear_cache(self, owner: str | None = None, repo: str | None = None) -> None:
        """
        Clear token cache.

        Args:
            owner: If specified, clear only tokens for this owner
            repo: If specified (with owner), clear only token for this specific repo
        """
        if owner and repo:
            cache_key = f"{owner}/{repo}"
            if cache_key in self._token_cache:
                del self._token_cache[cache_key]
                logger.info("token_cache_cleared", owner=owner, repo=repo)
        elif owner:
            # Clear all tokens for this owner
            keys_to_remove = [key for key in self._token_cache if key.startswith(f"{owner}/")]
            for key in keys_to_remove:
                del self._token_cache[key]
            logger.info("token_cache_cleared_owner", owner=owner, count=len(keys_to_remove))
        else:
            # Clear entire cache
            count = len(self._token_cache)
            self._token_cache.clear()
            logger.info("token_cache_cleared_all", count=count)
