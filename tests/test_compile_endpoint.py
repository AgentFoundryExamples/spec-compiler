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
Tests for compile endpoint.

Validates the /compile-spec endpoint behavior including request validation,
body size limits, logging, and response format.
"""

import json
import uuid

from fastapi.testclient import TestClient


def test_valid_compile_request_returns_202(test_client: TestClient) -> None:
    """Test that valid compile request returns 202 Accepted."""
    payload = {
        "plan_id": "plan-abc123",
        "spec_index": 0,
        "spec_data": {"type": "feature", "description": "Add authentication"},
        "github_owner": "my-org",
        "github_repo": "my-project",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202
    data = response.json()
    assert data["plan_id"] == "plan-abc123"
    assert data["spec_index"] == 0
    assert data["status"] == "accepted"
    assert "request_id" in data
    assert data["message"] == "Request accepted for processing"
    # Verify request_id is a valid UUID
    uuid.UUID(data["request_id"])


def test_compile_request_with_list_spec_data(test_client: TestClient) -> None:
    """Test compile request with list spec_data."""
    payload = {
        "plan_id": "plan-list",
        "spec_index": 1,
        "spec_data": [1, 2, 3, {"nested": "value"}],
        "github_owner": "test-org",
        "github_repo": "test-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202
    data = response.json()
    assert data["plan_id"] == "plan-list"
    assert data["spec_index"] == 1


def test_compile_request_with_empty_dict_spec_data(test_client: TestClient) -> None:
    """Test that empty dict spec_data succeeds."""
    payload = {
        "plan_id": "plan-empty",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_compile_request_with_spec_index_zero(test_client: TestClient) -> None:
    """Test that spec_index=0 is valid."""
    payload = {
        "plan_id": "plan-zero",
        "spec_index": 0,
        "spec_data": {"test": "data"},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202
    assert response.json()["spec_index"] == 0


def test_compile_request_adds_request_id_to_response_header(test_client: TestClient) -> None:
    """Test that response includes X-Request-Id header."""
    payload = {
        "plan_id": "plan-header",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202
    assert "X-Request-Id" in response.headers
    # Verify it's a valid UUID
    uuid.UUID(response.headers["X-Request-Id"])


def test_compile_request_propagates_request_id(test_client: TestClient) -> None:
    """Test that incoming X-Request-Id is propagated."""
    request_id = str(uuid.uuid4())
    headers = {"X-Request-Id": request_id}
    payload = {
        "plan_id": "plan-propagate",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload, headers=headers)

    assert response.status_code == 202
    assert response.headers["X-Request-Id"] == request_id
    assert response.json()["request_id"] == request_id


def test_compile_request_with_idempotency_key(test_client: TestClient) -> None:
    """Test that Idempotency-Key header is accepted."""
    headers = {"Idempotency-Key": "key-abc123"}
    payload = {
        "plan_id": "plan-idempotent",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload, headers=headers)

    assert response.status_code == 202
    # Note: Currently we just log the key, no deduplication logic yet
    assert response.json()["status"] == "accepted"


def test_compile_request_missing_plan_id_returns_422(test_client: TestClient) -> None:
    """Test that missing plan_id returns 422 validation error."""
    payload = {
        # Missing plan_id
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 422
    data = response.json()
    assert "detail" in data
    # Check that plan_id is mentioned in the error
    errors = data["detail"]
    assert any("plan_id" in str(error.get("loc", [])) for error in errors)


def test_compile_request_missing_github_owner_returns_422(test_client: TestClient) -> None:
    """Test that missing github_owner returns 422 validation error."""
    payload = {
        "plan_id": "plan-123",
        "spec_index": 0,
        "spec_data": {},
        # Missing github_owner
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 422
    data = response.json()
    errors = data["detail"]
    assert any("github_owner" in str(error.get("loc", [])) for error in errors)


def test_compile_request_missing_github_repo_returns_422(test_client: TestClient) -> None:
    """Test that missing github_repo returns 422 validation error."""
    payload = {
        "plan_id": "plan-123",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "owner",
        # Missing github_repo
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 422
    data = response.json()
    errors = data["detail"]
    assert any("github_repo" in str(error.get("loc", [])) for error in errors)


def test_compile_request_empty_plan_id_returns_422(test_client: TestClient) -> None:
    """Test that empty plan_id returns 422 validation error."""
    payload = {
        "plan_id": "",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 422
    data = response.json()
    errors = data["detail"]
    assert any("plan_id" in str(error.get("loc", [])) for error in errors)


def test_compile_request_whitespace_plan_id_returns_422(test_client: TestClient) -> None:
    """Test that whitespace-only plan_id returns 422 validation error."""
    payload = {
        "plan_id": "   ",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 422


def test_compile_request_whitespace_github_owner_returns_422(test_client: TestClient) -> None:
    """Test that whitespace-only github_owner returns 422 validation error."""
    payload = {
        "plan_id": "plan-123",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "  \t  ",
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 422


def test_compile_request_whitespace_github_repo_returns_422(test_client: TestClient) -> None:
    """Test that whitespace-only github_repo returns 422 validation error."""
    payload = {
        "plan_id": "plan-123",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "owner",
        "github_repo": "  \n  ",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 422


def test_compile_request_negative_spec_index_returns_422(test_client: TestClient) -> None:
    """Test that negative spec_index returns 422 validation error."""
    payload = {
        "plan_id": "plan-123",
        "spec_index": -1,
        "spec_data": {},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 422
    data = response.json()
    errors = data["detail"]
    assert any("spec_index" in str(error.get("loc", [])) for error in errors)


def test_compile_request_malformed_json_returns_422(test_client: TestClient) -> None:
    """Test that malformed JSON returns 422 error."""
    response = test_client.post(
        "/compile-spec",
        data="{ invalid json }",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422


def test_compile_request_body_size_limit_enforcement(test_client: TestClient) -> None:
    """Test that oversized request body returns 413 error."""
    # Import settings to get the configured limit
    from spec_compiler.config import settings

    # Create a large spec_data that exceeds the limit
    # Add 1MB buffer to ensure we exceed the limit
    large_data = {"large_field": "x" * (settings.max_request_body_size_bytes + 1_000_000)}
    payload = {
        "plan_id": "plan-large",
        "spec_index": 0,
        "spec_data": large_data,
        "github_owner": "owner",
        "github_repo": "repo",
    }

    # Need to manually set Content-Length header to trigger the check
    payload_json = json.dumps(payload)
    headers = {
        "Content-Type": "application/json",
        "Content-Length": str(len(payload_json)),
    }

    response = test_client.post("/compile-spec", data=payload_json, headers=headers)

    assert response.status_code == 413
    data = response.json()
    assert "detail" in data
    assert "exceeds maximum size limit" in data["detail"]


def test_compile_request_complex_nested_spec_data(test_client: TestClient) -> None:
    """Test compile request with complex nested spec_data."""
    payload = {
        "plan_id": "plan-complex",
        "spec_index": 5,
        "spec_data": {
            "level1": {
                "level2": [
                    {"item": 1, "data": [1, 2, 3]},
                    {"item": 2, "data": {"nested": True}},
                ],
                "metadata": {"version": "1.0", "tags": ["a", "b", "c"]},
            }
        },
        "github_owner": "complex-owner",
        "github_repo": "complex-repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202
    data = response.json()
    assert data["plan_id"] == "plan-complex"
    assert data["spec_index"] == 5


def test_compile_request_response_has_all_required_fields(test_client: TestClient) -> None:
    """Test that response contains all required CompileResponse fields."""
    payload = {
        "plan_id": "plan-fields",
        "spec_index": 2,
        "spec_data": {"test": "data"},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202
    data = response.json()

    # Check all required fields are present
    assert "request_id" in data
    assert "plan_id" in data
    assert "spec_index" in data
    assert "status" in data

    # Check field values
    assert data["plan_id"] == "plan-fields"
    assert data["spec_index"] == 2
    assert data["status"] in ["accepted", "failed"]


def test_compile_endpoint_in_openapi_spec(test_client: TestClient) -> None:
    """Test that compile endpoint is documented in OpenAPI spec."""
    response = test_client.get("/openapi.json")

    assert response.status_code == 200
    openapi_spec = response.json()

    # Check that /compile-spec endpoint is documented
    assert "/compile-spec" in openapi_spec["paths"]
    assert "post" in openapi_spec["paths"]["/compile-spec"]

    # Check response codes are documented
    compile_endpoint = openapi_spec["paths"]["/compile-spec"]["post"]
    assert "202" in compile_endpoint["responses"]
    assert "413" in compile_endpoint["responses"]
    assert "422" in compile_endpoint["responses"]


def test_multiple_requests_with_same_idempotency_key(test_client: TestClient) -> None:
    """Test that multiple requests with same idempotency key are handled."""
    headers = {"Idempotency-Key": "duplicate-key-123"}
    payload = {
        "plan_id": "plan-dup",
        "spec_index": 0,
        "spec_data": {},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    # First request
    response1 = test_client.post("/compile-spec", json=payload, headers=headers)
    assert response1.status_code == 202

    # Second request with same key
    response2 = test_client.post("/compile-spec", json=payload, headers=headers)
    assert response2.status_code == 202

    # Note: Currently we don't deduplicate, just log the key
    # Both requests should succeed independently


def test_compile_request_without_content_length_header(test_client: TestClient) -> None:
    """Test that request without Content-Length header is handled gracefully."""
    payload = {
        "plan_id": "plan-no-length",
        "spec_index": 0,
        "spec_data": {"test": "data"},
        "github_owner": "owner",
        "github_repo": "repo",
    }

    # TestClient may add Content-Length automatically, but the endpoint
    # should handle missing header gracefully
    response = test_client.post("/compile-spec", json=payload)

    assert response.status_code == 202
