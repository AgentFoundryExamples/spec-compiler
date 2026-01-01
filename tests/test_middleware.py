"""
Tests for middleware functionality.

Validates request ID middleware behavior and edge cases.
"""

import uuid

from fastapi.testclient import TestClient


def test_middleware_generates_uuid_for_missing_header(test_client: TestClient) -> None:
    """Test that middleware generates UUID when header is missing."""
    response = test_client.get("/health")

    assert "X-Request-Id" in response.headers
    # Verify it's a valid UUID
    request_id = response.headers["X-Request-Id"]
    uuid.UUID(request_id)


def test_middleware_propagates_valid_uuid(test_client: TestClient) -> None:
    """Test that middleware propagates valid UUID."""
    request_id = str(uuid.uuid4())
    response = test_client.get("/health", headers={"X-Request-Id": request_id})

    assert response.headers["X-Request-Id"] == request_id


def test_middleware_rejects_invalid_uuid(test_client: TestClient) -> None:
    """Test that middleware generates new UUID for invalid format."""
    response = test_client.get("/health", headers={"X-Request-Id": "invalid-uuid"})

    assert "X-Request-Id" in response.headers
    # Should be a valid UUID (not the invalid one we sent)
    new_id = response.headers["X-Request-Id"]
    uuid.UUID(new_id)
    assert new_id != "invalid-uuid"


def test_middleware_rejects_oversized_uuid(test_client: TestClient) -> None:
    """Test that middleware generates new UUID for oversized input."""
    large_string = "a" * 500
    response = test_client.get("/health", headers={"X-Request-Id": large_string})

    assert "X-Request-Id" in response.headers
    # Should be a valid UUID (not the oversized string)
    new_id = response.headers["X-Request-Id"]
    uuid.UUID(new_id)
    assert len(new_id) == 36  # Standard UUID length


def test_middleware_handles_empty_header(test_client: TestClient) -> None:
    """Test that middleware generates UUID for empty header value."""
    response = test_client.get("/health", headers={"X-Request-Id": ""})

    assert "X-Request-Id" in response.headers
    request_id = response.headers["X-Request-Id"]
    uuid.UUID(request_id)


def test_middleware_case_insensitive_header(test_client: TestClient) -> None:
    """Test that middleware handles case-insensitive header names."""
    request_id = str(uuid.uuid4())
    # Send with different casing
    response = test_client.get("/health", headers={"x-request-id": request_id})

    assert response.headers["X-Request-Id"] == request_id


def test_middleware_adds_request_id_to_all_endpoints(test_client: TestClient) -> None:
    """Test that request ID is added to all endpoints."""
    health_response = test_client.get("/health")
    version_response = test_client.get("/version")

    assert "X-Request-Id" in health_response.headers
    assert "X-Request-Id" in version_response.headers

    # Each request should get a unique ID
    uuid.UUID(health_response.headers["X-Request-Id"])
    uuid.UUID(version_response.headers["X-Request-Id"])
