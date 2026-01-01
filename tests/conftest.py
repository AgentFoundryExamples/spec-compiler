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

import pytest
from fastapi.testclient import TestClient

from spec_compiler.app.main import create_app


@pytest.fixture
def test_client() -> TestClient:
    """
    Create a test client for the FastAPI application.

    Returns:
        TestClient instance for making test requests
    """
    app = create_app()
    return TestClient(app)


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

    return TestClient(app)
