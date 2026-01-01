"""
Tests for health check endpoint.

Validates the /health endpoint returns correct status and handles
request ID middleware properly.
"""

import uuid

import pytest
from fastapi.testclient import TestClient


def test_health_check_returns_ok(test_client: TestClient) -> None:
    """Test that /health endpoint returns status ok."""
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_adds_request_id_to_response(test_client: TestClient) -> None:
    """Test that health check adds X-Request-Id to response headers."""
    response = test_client.get("/health")

    assert "X-Request-Id" in response.headers
    # Verify it's a valid UUID format
    request_id = response.headers["X-Request-Id"]
    try:
        uuid.UUID(request_id)
    except ValueError:
        pytest.fail(f"Request ID '{request_id}' is not a valid UUID")


def test_health_check_propagates_request_id(test_client: TestClient) -> None:
    """Test that health check propagates incoming X-Request-Id."""
    request_id = str(uuid.uuid4())
    headers = {"X-Request-Id": request_id}

    response = test_client.get("/health", headers=headers)

    assert response.status_code == 200
    assert response.headers["X-Request-Id"] == request_id


def test_health_check_generates_request_id_when_missing(test_client: TestClient) -> None:
    """Test that health check generates request ID when header is missing."""
    response = test_client.get("/health")

    assert "X-Request-Id" in response.headers
    # Should be a valid UUID
    request_id = response.headers["X-Request-Id"]
    uuid.UUID(request_id)  # Will raise ValueError if invalid


def test_health_check_handles_malformed_request_id(test_client: TestClient) -> None:
    """Test that health check handles malformed request ID gracefully."""
    headers = {"X-Request-Id": "not-a-valid-uuid"}

    response = test_client.get("/health", headers=headers)

    assert response.status_code == 200
    # Should generate a new valid UUID instead of using malformed one
    request_id = response.headers["X-Request-Id"]
    uuid.UUID(request_id)  # Will raise ValueError if invalid


def test_health_check_handles_oversized_request_id(test_client: TestClient) -> None:
    """Test that health check handles oversized request ID."""
    headers = {"X-Request-Id": "x" * 200}  # Very long string

    response = test_client.get("/health", headers=headers)

    assert response.status_code == 200
    # Should generate a new valid UUID
    request_id = response.headers["X-Request-Id"]
    uuid.UUID(request_id)


def test_version_endpoint_returns_info(test_client: TestClient) -> None:
    """Test that /version endpoint returns version information."""
    response = test_client.get("/version")

    assert response.status_code == 200
    data = response.json()

    assert "version" in data
    assert "git_sha" in data
    assert "environment" in data
    assert data["environment"] == "development"


def test_openapi_json_accessible(test_client: TestClient) -> None:
    """Test that OpenAPI JSON schema is accessible."""
    response = test_client.get("/openapi.json")

    assert response.status_code == 200
    # Verify it's valid JSON
    openapi_spec = response.json()
    assert "openapi" in openapi_spec
    assert "info" in openapi_spec
    assert "paths" in openapi_spec


def test_docs_endpoint_accessible(test_client: TestClient) -> None:
    """Test that Swagger UI docs are accessible."""
    response = test_client.get("/docs")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
