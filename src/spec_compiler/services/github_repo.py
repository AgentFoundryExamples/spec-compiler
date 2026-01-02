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
GitHub repository client for fetching files and data.

Provides GitHubRepoClient for accessing GitHub repository contents
via the GitHub API, with base64 decoding and JSON parsing.
"""

import base64
import json
from typing import Any

import httpx

from spec_compiler.config import settings
from spec_compiler.logging import get_logger

logger = get_logger(__name__)


class GitHubFileError(Exception):
    """
    Exception raised when GitHub file operations fail.

    Attributes:
        message: Human-readable error message
        status_code: HTTP status code if applicable
        response_body: Raw response body for debugging (sanitized)
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
        # Sanitize response to prevent token leakage
        self.response_body = self._sanitize_response(response_body) if response_body else None
        self.context = context or {}

    @staticmethod
    def _sanitize_response(response_body: str) -> str:
        """Sanitize response body to prevent sensitive data leakage."""
        import re

        truncated = response_body[:500]
        # Redact potential token patterns in error responses
        truncated = re.sub(
            r"(Bearer\s+)([A-Za-z0-9_\-\.]+)", r"\1[REDACTED]", truncated, flags=re.IGNORECASE
        )
        return truncated


class InvalidJSONError(Exception):
    """
    Exception raised when JSON content is malformed or invalid.

    Attributes:
        message: Human-readable error message
        content: The invalid content that failed to parse
        context: Additional context about the error
    """

    def __init__(
        self,
        message: str,
        content: str | None = None,
        context: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.content = content
        self.context = context or {}


class GitHubRepoClient:
    """
    Client for fetching files and data from GitHub repositories.

    This client uses the GitHub Contents API to retrieve files,
    decode base64 content, and parse JSON. It handles various
    error conditions and provides structured logging.
    """

    def __init__(
        self,
        github_api_base_url: str | None = None,
        timeout: float = 30.0,
    ):
        """
        Initialize the GitHub repository client.

        Args:
            github_api_base_url: Base URL for GitHub API (defaults to config)
            timeout: HTTP request timeout in seconds
        """
        self.github_api_base_url = github_api_base_url or settings.github_api_base_url
        self.timeout = timeout

    def get_json_file(
        self,
        owner: str,
        repo: str,
        path: str,
        token: str | None = None,
    ) -> dict[str, Any]:
        """
        Get and parse a JSON file from a GitHub repository.

        Performs GET /repos/{owner}/{repo}/contents/{path}, decodes
        base64 content, parses JSON, and returns the parsed dict.

        Args:
            owner: GitHub repository owner
            repo: GitHub repository name
            path: Path to the file in the repository
            token: Optional GitHub access token for authentication

        Returns:
            Parsed JSON content as a dictionary

        Raises:
            GitHubFileError: For HTTP errors (4xx/5xx status codes)
            InvalidJSONError: For malformed JSON content
        """
        # Prepare request
        url = f"{self.github_api_base_url.rstrip('/')}/repos/{owner}/{repo}/contents/{path}"
        headers: dict[str, str] = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

        if token:
            # Validate token to prevent header injection
            if "\n" in token or "\r" in token:
                raise GitHubFileError(
                    "Invalid token: contains newline characters",
                    context={"owner": owner, "repo": repo, "path": path},
                )
            headers["Authorization"] = f"Bearer {token}"

        logger.info(
            "github_file_request",
            owner=owner,
            repo=repo,
            path=path,
            url=url,
            authenticated=token is not None,
        )

        try:
            # Make HTTP request to GitHub API with TLS verification
            with httpx.Client(timeout=self.timeout, verify=True) as client:
                response = client.get(url, headers=headers)

            # Check for HTTP errors
            if response.status_code != 200:
                error_msg = f"GitHub API returned status {response.status_code}"
                logger.error(
                    "github_file_http_error",
                    owner=owner,
                    repo=repo,
                    path=path,
                    status_code=response.status_code,
                    response_text=response.text[:500],  # Truncate for logging
                )
                raise GitHubFileError(
                    error_msg,
                    status_code=response.status_code,
                    response_body=response.text,
                    context={"owner": owner, "repo": repo, "path": path},
                )

            # Parse response JSON
            try:
                response_data = response.json()
            except Exception as e:
                error_msg = f"Failed to parse GitHub API response as JSON: {e}"
                logger.error(
                    "github_response_json_parse_error",
                    owner=owner,
                    repo=repo,
                    path=path,
                    error=str(e),
                    response_text=response.text[:500],
                )
                raise GitHubFileError(
                    error_msg,
                    status_code=response.status_code,
                    response_body=response.text,
                    context={"owner": owner, "repo": repo, "path": path, "parse_error": str(e)},
                ) from e

            # Check if content is base64 encoded
            content = response_data.get("content")
            encoding = response_data.get("encoding")

            if encoding == "base64":
                # Decode base64 content
                if not content:
                    error_msg = "GitHub API response missing 'content' field"
                    logger.error(
                        "github_missing_content_field",
                        owner=owner,
                        repo=repo,
                        path=path,
                        response_keys=list(response_data.keys()),
                    )
                    raise GitHubFileError(
                        error_msg,
                        status_code=response.status_code,
                        response_body=response.text,
                        context={
                            "owner": owner,
                            "repo": repo,
                            "path": path,
                            "missing_field": "content",
                        },
                    )

                try:
                    # Remove whitespace and decode base64
                    content_bytes = base64.b64decode(content.replace("\n", "").replace(" ", ""))
                    decoded_content = content_bytes.decode("utf-8")
                except Exception as e:
                    error_msg = f"Failed to decode base64 content: {e}"
                    logger.error(
                        "github_base64_decode_error",
                        owner=owner,
                        repo=repo,
                        path=path,
                        error=str(e),
                    )
                    raise GitHubFileError(
                        error_msg,
                        status_code=response.status_code,
                        response_body=response.text,
                        context={
                            "owner": owner,
                            "repo": repo,
                            "path": path,
                            "decode_error": str(e),
                        },
                    ) from e

            elif encoding is None or encoding == "":
                # Content is already plain text (uncommon but possible)
                # Validate that content field exists and is a string
                if content is None:
                    error_msg = "GitHub API response has no encoding but content is null"
                    logger.error(
                        "github_plaintext_missing_content",
                        owner=owner,
                        repo=repo,
                        path=path,
                    )
                    raise GitHubFileError(
                        error_msg,
                        status_code=response.status_code,
                        response_body=response.text,
                        context={"owner": owner, "repo": repo, "path": path},
                    )
                if not isinstance(content, str):
                    error_msg = (
                        f"GitHub API response content is not a string: {type(content).__name__}"
                    )
                    logger.error(
                        "github_plaintext_invalid_type",
                        owner=owner,
                        repo=repo,
                        path=path,
                        content_type=type(content).__name__,
                    )
                    raise GitHubFileError(
                        error_msg,
                        status_code=response.status_code,
                        response_body=response.text,
                        context={
                            "owner": owner,
                            "repo": repo,
                            "path": path,
                            "content_type": type(content).__name__,
                        },
                    )
                decoded_content = content
                logger.info(
                    "github_plaintext_content",
                    owner=owner,
                    repo=repo,
                    path=path,
                    encoding=encoding,
                )
            else:
                # Unexpected encoding
                error_msg = f"Unexpected encoding format: {encoding}"
                logger.error(
                    "github_unexpected_encoding",
                    owner=owner,
                    repo=repo,
                    path=path,
                    encoding=encoding,
                )
                raise GitHubFileError(
                    error_msg,
                    status_code=response.status_code,
                    response_body=response.text,
                    context={"owner": owner, "repo": repo, "path": path, "encoding": encoding},
                )

            # Parse JSON content
            try:
                json_data = json.loads(decoded_content)
            except json.JSONDecodeError as e:
                error_msg = f"Failed to parse JSON content: {e}"
                logger.error(
                    "github_json_parse_error",
                    owner=owner,
                    repo=repo,
                    path=path,
                    error=str(e),
                    content_preview=decoded_content[:200],  # Show preview for debugging
                )
                raise InvalidJSONError(
                    error_msg,
                    content=decoded_content,
                    context={
                        "owner": owner,
                        "repo": repo,
                        "path": path,
                        "json_error": str(e),
                    },
                ) from e

            # Validate that result is a dict (requirement from issue)
            if not isinstance(json_data, dict):
                error_msg = f"Expected JSON object (dict), got {type(json_data).__name__}"
                logger.error(
                    "github_json_type_error",
                    owner=owner,
                    repo=repo,
                    path=path,
                    actual_type=type(json_data).__name__,
                )
                raise InvalidJSONError(
                    error_msg,
                    content=decoded_content,
                    context={
                        "owner": owner,
                        "repo": repo,
                        "path": path,
                        "expected_type": "dict",
                        "actual_type": type(json_data).__name__,
                    },
                )

            logger.info(
                "github_file_success",
                owner=owner,
                repo=repo,
                path=path,
                size=len(decoded_content),
                json_keys=list(json_data.keys()) if isinstance(json_data, dict) else None,
            )

            return json_data

        except httpx.HTTPError as e:
            error_msg = f"HTTP error during GitHub API request: {e}"
            logger.error(
                "github_http_exception",
                owner=owner,
                repo=repo,
                path=path,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise GitHubFileError(
                error_msg,
                context={"owner": owner, "repo": repo, "path": path, "exception": str(e)},
            ) from e
        except (GitHubFileError, InvalidJSONError):
            # Re-raise our custom exceptions as-is
            raise
        except Exception as e:
            error_msg = f"Unexpected error during GitHub file fetch: {e}"
            logger.error(
                "github_unexpected_error",
                owner=owner,
                repo=repo,
                path=path,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise GitHubFileError(
                error_msg,
                context={"owner": owner, "repo": repo, "path": path, "exception": str(e)},
            ) from e


def create_fallback_tree() -> list[dict[str, Any]]:
    """
    Create a fallback tree payload when repository tree cannot be fetched.

    Returns:
        List with a single placeholder entry indicating unavailable data
    """
    return [
        {
            "path": ".",
            "type": "tree",
            "mode": "040000",
            "sha": "unavailable",
            "url": "unavailable",
            "note": "Repository tree data unavailable",
        }
    ]


def create_fallback_dependencies() -> list[dict[str, Any]]:
    """
    Create a fallback dependencies payload when dependencies cannot be fetched.

    Returns:
        List with a single placeholder entry indicating unavailable data
    """
    return [
        {
            "name": "unknown",
            "version": "unknown",
            "ecosystem": "unknown",
            "note": "Dependency data unavailable",
        }
    ]


def create_fallback_file_summaries() -> list[dict[str, Any]]:
    """
    Create a fallback file summaries payload when summaries cannot be generated.

    Returns:
        List with a single placeholder entry indicating unavailable data
    """
    return [
        {
            "path": "unknown",
            "summary": "File summary data unavailable",
            "lines": 0,
            "note": "Unable to fetch or summarize repository files",
        }
    ]
