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

Provides shared test fixtures for the test suite, including publisher mocks
for status publishing tests.

**Note on Background Task Testing:**
FastAPI's TestClient executes background tasks synchronously before returning
the response, ensuring that all background work completes before test assertions.
This is different from production where BackgroundTasks execute truly asynchronously.
For production-like async testing, consider using async test clients or integration tests.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from spec_compiler.app.main import create_app
from spec_compiler.models import GitHubAuthToken, PlanStatusMessage


@pytest.fixture
def test_client() -> TestClient:
    """
    Create a test client for the FastAPI application.

    Returns:
        TestClient instance for making test requests
    """
    # Mock GitHub clients to avoid needing real minting service in tests
    # Enable LLM stub mode to avoid needing API keys
    with (
        patch("spec_compiler.app.routes.compile.GitHubAuthClient") as mock_auth_class,
        patch("spec_compiler.app.routes.compile.GitHubRepoClient") as mock_repo_class,
        patch("spec_compiler.config.settings.llm_stub_mode", True),
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
    # Enable LLM stub mode to avoid needing API keys
    with (
        patch("spec_compiler.app.routes.compile.GitHubAuthClient") as mock_auth_class,
        patch("spec_compiler.app.routes.compile.GitHubRepoClient") as mock_repo_class,
        patch("spec_compiler.config.settings.llm_stub_mode", True),
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


class PublisherMock:
    """
    Mock publisher that captures published messages for testing.

    This mock provides a way to verify that status messages were published
    with the correct content and in the correct order.
    """

    def __init__(self):
        self.messages: list[PlanStatusMessage] = []
        self.call_count = 0
        self.should_raise = None

    def publish_status(self, message: PlanStatusMessage, ordering_key: str | None = None) -> None:
        """Mock publish_status that captures messages."""
        self.call_count += 1
        self.messages.append(message)

        if self.should_raise:
            raise self.should_raise

    def get_messages_by_status(self, status: str) -> list[PlanStatusMessage]:
        """Get all messages with a specific status."""
        return [msg for msg in self.messages if msg.status == status]

    def get_messages_by_plan(self, plan_id: str) -> list[PlanStatusMessage]:
        """Get all messages for a specific plan."""
        return [msg for msg in self.messages if msg.plan_id == plan_id]

    def clear(self) -> None:
        """Clear captured messages."""
        self.messages.clear()
        self.call_count = 0
        self.should_raise = None


@pytest.fixture
def mock_publisher():
    """
    Provide a PublisherMock that captures status messages.

    Example usage:
        def test_something(mock_publisher):
            # Make API call that publishes status
            response = client.post(...)

            # Verify messages were published
            assert mock_publisher.call_count == 2
            assert len(mock_publisher.get_messages_by_status("in_progress")) == 1
            assert len(mock_publisher.get_messages_by_status("succeeded")) == 1
    """
    mock = PublisherMock()
    with patch("spec_compiler.app.routes.compile.get_publisher", return_value=mock):
        with patch("spec_compiler.middleware.error_handler.get_publisher", return_value=mock):
            yield mock


@pytest.fixture
def mock_publisher_disabled():
    """
    Provide a disabled publisher (returns None) for testing graceful degradation.

    Example usage:
        def test_compile_without_publisher(mock_publisher_disabled):
            # API should still work even without publisher configured
            response = client.post(...)
            assert response.status_code == 202
    """
    with patch("spec_compiler.app.routes.compile.get_publisher", return_value=None):
        with patch("spec_compiler.middleware.error_handler.get_publisher", return_value=None):
            yield
