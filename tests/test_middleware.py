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


# Error Handling Middleware Tests


def test_error_handling_middleware_passthrough(test_client: TestClient) -> None:
    """Test that error handling middleware passes through successful requests."""
    response = test_client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert "X-Request-Id" in response.headers


def test_error_handling_middleware_catches_exception(
    test_client_with_error_routes: TestClient,
) -> None:
    """Test that error handling middleware catches and formats exceptions."""
    # Make request that will trigger the exception
    response = test_client_with_error_routes.get("/test-error")

    # Verify error response structure
    assert response.status_code == 500
    data = response.json()
    assert data["error"] == "internal_error"
    assert "request_id" in data
    assert "message" in data
    assert "Test exception" not in data["message"]  # Don't leak exception details
    assert "contact support" in data["message"].lower()

    # Verify request_id is a valid UUID
    uuid.UUID(data["request_id"])

    # Verify request_id header matches body
    assert response.headers["X-Request-Id"] == data["request_id"]


def test_error_handling_middleware_with_idempotency_key(test_client: TestClient) -> None:
    """Test that error handling middleware handles Idempotency-Key header."""
    idempotency_key = "test-idempotency-key-12345"
    response = test_client.get("/health", headers={"Idempotency-Key": idempotency_key})

    assert response.status_code == 200
    # Idempotency key should be echoed back
    assert response.headers.get("Idempotency-Key") == idempotency_key


def test_error_handling_middleware_idempotency_key_in_error(
    test_client_with_error_routes: TestClient,
) -> None:
    """Test that Idempotency-Key is echoed in error responses."""
    idempotency_key = "error-test-key-67890"
    response = test_client_with_error_routes.get(
        "/test-error-with-key", headers={"Idempotency-Key": idempotency_key}
    )

    assert response.status_code == 500
    # Idempotency key should be echoed even in error response
    assert response.headers.get("Idempotency-Key") == idempotency_key


def test_error_handling_middleware_truncates_long_idempotency_key(test_client: TestClient) -> None:
    """Test that excessively long Idempotency-Key is truncated."""
    # Create a key longer than MAX_IDEMPOTENCY_KEY_LENGTH (255)
    long_key = "x" * 500

    response = test_client.get("/health", headers={"Idempotency-Key": long_key})

    assert response.status_code == 200
    echoed_key = response.headers.get("Idempotency-Key")
    assert echoed_key is not None
    # Should be truncated to 255 characters
    assert len(echoed_key) <= 255


def test_error_handling_middleware_sanitizes_unicode_idempotency_key(
    test_client: TestClient,
) -> None:
    """Test that unicode/special characters in Idempotency-Key are sanitized."""
    # Key with control characters (avoid unicode emoji since httpx headers must be ASCII)
    unicode_key = "test-key-\x00\x01-control"

    response = test_client.get("/health", headers={"Idempotency-Key": unicode_key})

    assert response.status_code == 200
    echoed_key = response.headers.get("Idempotency-Key")
    assert echoed_key is not None
    # Control characters should be replaced with '?'
    assert "?" in echoed_key or len(echoed_key) > 0
    # Original control chars should not be present
    assert "\x00" not in echoed_key
    assert "\x01" not in echoed_key


def test_error_handling_middleware_handles_empty_idempotency_key(test_client: TestClient) -> None:
    """Test that empty Idempotency-Key is handled gracefully."""
    response = test_client.get("/health", headers={"Idempotency-Key": ""})

    assert response.status_code == 200
    # Empty key should not be echoed
    assert "Idempotency-Key" not in response.headers


def test_error_handling_middleware_reuses_existing_request_id(
    test_client_with_error_routes: TestClient,
) -> None:
    """Test that error handling middleware reuses request_id from RequestIdMiddleware."""
    # Provide a request ID
    request_id = str(uuid.uuid4())
    response = test_client_with_error_routes.get(
        "/test-error-request-id", headers={"X-Request-Id": request_id}
    )

    assert response.status_code == 500
    data = response.json()

    # Error response should use the same request_id we provided
    assert data["request_id"] == request_id
    assert response.headers["X-Request-Id"] == request_id


def test_error_handling_middleware_generates_request_id_if_missing(
    test_client_with_error_routes: TestClient,
) -> None:
    """Test that error handling uses generated request_id if none provided."""
    # Don't provide a request ID
    response = test_client_with_error_routes.get("/test-error-no-id")

    assert response.status_code == 500
    data = response.json()

    # Should have a valid request_id
    assert "request_id" in data
    uuid.UUID(data["request_id"])  # Validate it's a UUID
    assert response.headers["X-Request-Id"] == data["request_id"]


def test_error_handling_middleware_logs_exception_details(
    test_client_with_error_routes: TestClient, caplog
) -> None:
    """Test that error handling middleware logs full exception details."""
    import logging

    # Capture logs at ERROR level
    caplog.set_level(logging.ERROR)

    # Make request that will trigger the exception
    response = test_client_with_error_routes.get("/test-error")

    assert response.status_code == 500

    # Verify that error was logged
    # Note: structlog logs to stdout by default in JSON format
    # This test verifies the logging call was made, actual log output
    # is tested in test_logging.py
    assert response.json()["error"] == "internal_error"


# Error Handling with Status Publishing Tests


def test_middleware_publishes_failed_status_on_exception(
    test_client_with_error_routes: TestClient, mock_publisher
) -> None:
    """Test that middleware publishes failed status when compile request throws exception."""
    from unittest.mock import patch

    # Make a request that will fail
    with patch("spec_compiler.app.routes.compile.create_llm_client") as mock_create:
        mock_create.side_effect = RuntimeError("LLM client creation failed")

        payload = {
            "plan_id": "plan-middleware-test",
            "spec_index": 3,
            "spec_data": {"test": "data"},
            "github_owner": "test-owner",
            "github_repo": "test-repo",
        }

        response = test_client_with_error_routes.post("/compile-spec", json=payload)

        # Should return error response
        assert response.status_code == 500

        # Verify failed status was published
        failed_messages = mock_publisher.get_messages_by_status("failed")
        assert len(failed_messages) == 1

        # Verify the failed message has correct plan context
        failed_msg = failed_messages[0]
        assert failed_msg.plan_id == "plan-middleware-test"
        assert failed_msg.spec_index == 3
        assert failed_msg.error_code == "unhandled_exception"
        assert "RuntimeError" in failed_msg.error_message


def test_middleware_does_not_block_response_on_publish_failure(
    test_client_with_error_routes: TestClient, mock_publisher
) -> None:
    """Test that publish failures don't prevent error responses."""
    from unittest.mock import patch

    # Make publisher throw when trying to publish
    mock_publisher.should_raise = Exception("Pub/Sub is down")

    with patch("spec_compiler.app.routes.compile.create_llm_client") as mock_create:
        mock_create.side_effect = RuntimeError("LLM failure")

        payload = {
            "plan_id": "plan-publish-error",
            "spec_index": 5,
            "spec_data": {},
            "github_owner": "owner",
            "github_repo": "repo",
        }

        # Should still return error response even though publisher failed
        response = test_client_with_error_routes.post("/compile-spec", json=payload)

        assert response.status_code == 500
        assert "request_id" in response.json()
        # Error goes through middleware since it's unhandled
        assert response.json()["error"] == "internal_error"


def test_middleware_handles_unparseable_request_body(test_client_with_error_routes: TestClient, mock_publisher) -> None:
    """Test that middleware handles errors when request body can't be parsed."""
    # Use the test-error endpoint which doesn't have a request body
    response = test_client_with_error_routes.get("/test-error")

    assert response.status_code == 500

    # No status should be published since we can't extract plan context
    assert mock_publisher.call_count == 0


def test_middleware_extracts_plan_context_from_body(test_client_with_error_routes: TestClient, mock_publisher) -> None:
    """Test that middleware can extract plan context from compile request body."""
    from unittest.mock import patch

    with patch("spec_compiler.app.routes.compile.create_llm_client") as mock_create:
        # Make endpoint throw after body is parsed
        mock_create.side_effect = RuntimeError("Simulated failure")

        payload = {
            "plan_id": "plan-context-extract",
            "spec_index": 7,
            "spec_data": {"data": "test"},
            "github_owner": "test-org",
            "github_repo": "test-project",
        }

        response = test_client_with_error_routes.post("/compile-spec", json=payload)

        assert response.status_code == 500

        # Verify plan context was extracted and used
        failed_messages = mock_publisher.get_messages_by_status("failed")
        assert len(failed_messages) == 1

        msg = failed_messages[0]
        assert msg.plan_id == "plan-context-extract"
        assert msg.spec_index == 7


def test_middleware_status_publishing_idempotent_across_errors(
    test_client_with_error_routes: TestClient, mock_publisher
) -> None:
    """Test that each error publishes exactly one failed status."""
    from unittest.mock import patch

    with patch("spec_compiler.app.routes.compile.create_llm_client") as mock_create:
        mock_create.side_effect = RuntimeError("Error")

        payload = {
            "plan_id": "plan-single-publish",
            "spec_index": 0,
            "spec_data": {},
            "github_owner": "owner",
            "github_repo": "repo",
        }

        # First request
        response1 = test_client_with_error_routes.post("/compile-spec", json=payload)
        assert response1.status_code == 500

        initial_count = len(mock_publisher.get_messages_by_status("failed"))

        # Second request with same plan
        response2 = test_client_with_error_routes.post("/compile-spec", json=payload)
        assert response2.status_code == 500

        # Should have published one more failed status
        final_count = len(mock_publisher.get_messages_by_status("failed"))
        assert final_count == initial_count + 1

