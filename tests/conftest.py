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
