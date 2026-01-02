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
Pytest configuration and fixtures.

Provides shared test fixtures for the test suite.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from spec_compiler.app.main import create_app
from spec_compiler.models import GitHubAuthToken


@pytest.fixture
def test_client() -> TestClient:
    """
    Create a test client for the FastAPI application.

    Returns:
        TestClient instance for making test requests
    """
    # Mock GitHub clients to avoid needing real minting service in tests
    with (
        patch("spec_compiler.app.routes.compile.GitHubAuthClient") as mock_auth_class,
        patch("spec_compiler.app.routes.compile.GitHubRepoClient") as mock_repo_class,
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


@pytest.fixture
def test_app():
    """
    Create a FastAPI application instance for testing.

    Returns:
        FastAPI application instance
    """
    return create_app()


@pytest.fixture
def test_client_with_error_routes() -> TestClient:
    """
    Create a test client with additional error test routes.

    Returns:
        TestClient instance with error test endpoints
    """
    # Mock GitHub clients
    with (
        patch("spec_compiler.app.routes.compile.GitHubAuthClient") as mock_auth_class,
        patch("spec_compiler.app.routes.compile.GitHubRepoClient") as mock_repo_class,
    ):

        mock_auth_instance = MagicMock()
        mock_auth_class.return_value = mock_auth_instance
        mock_token = GitHubAuthToken(
            access_token="gho_test_token",
            token_type="bearer",
        )
        mock_auth_instance.mint_user_to_server_token.return_value = mock_token

        mock_repo_instance = MagicMock()
        mock_repo_class.return_value = mock_repo_instance
        mock_repo_instance.get_json_file.return_value = {}

        app = create_app()

        # Add test routes that raise exceptions
        @app.get("/test-error")
        async def test_error_endpoint():
            raise ValueError("Test exception for error handling")

        @app.get("/test-error-with-key")
        async def test_error_with_key():
            raise RuntimeError("Test error with idempotency key")

        @app.get("/test-error-request-id")
        async def test_error_request_id():
            raise Exception("Test error for request_id reuse")

        @app.get("/test-error-no-id")
        async def test_error_no_id():
            raise Exception("Test error without request_id")

        yield TestClient(app)
