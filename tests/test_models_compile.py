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
Tests for compile API models.

Validates CompileRequest and CompileResponse models including validation
rules and edge cases.
"""

import pytest
from pydantic import ValidationError

from spec_compiler.models.compile import CompileRequest, CompileResponse


class TestCompileRequest:
    """Tests for CompileRequest model."""

    def test_valid_request_with_dict_spec_data(self) -> None:
        """Test valid request with dict spec_data."""
        request = CompileRequest(
            plan_id="plan-123",
            spec_index=0,
            spec_data={"key": "value", "nested": {"data": 123}},
            github_owner="example-owner",
            github_repo="example-repo",
        )
        assert request.plan_id == "plan-123"
        assert request.spec_index == 0
        assert request.spec_data == {"key": "value", "nested": {"data": 123}}
        assert request.github_owner == "example-owner"
        assert request.github_repo == "example-repo"

    def test_valid_request_with_list_spec_data(self) -> None:
        """Test valid request with list spec_data."""
        request = CompileRequest(
            plan_id="plan-456",
            spec_index=5,
            spec_data=[1, 2, {"nested": "value"}],
            github_owner="test-org",
            github_repo="test-repo",
        )
        assert request.spec_index == 5
        assert request.spec_data == [1, 2, {"nested": "value"}]

    def test_spec_index_zero_is_valid(self) -> None:
        """Test that spec_index can be zero."""
        request = CompileRequest(
            plan_id="plan-0",
            spec_index=0,
            spec_data={},
            github_owner="owner",
            github_repo="repo",
        )
        assert request.spec_index == 0

    def test_spec_index_negative_raises_validation_error(self) -> None:
        """Test that negative spec_index raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileRequest(
                plan_id="plan-123",
                spec_index=-1,
                spec_data={},
                github_owner="owner",
                github_repo="repo",
            )
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("spec_index",) and error["type"] == "greater_than_equal"
            for error in errors
        )

    def test_plan_id_empty_string_raises_validation_error(self) -> None:
        """Test that empty plan_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileRequest(
                plan_id="",
                spec_index=0,
                spec_data={},
                github_owner="owner",
                github_repo="repo",
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("plan_id",) for error in errors)

    def test_plan_id_whitespace_only_raises_validation_error(self) -> None:
        """Test that whitespace-only plan_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileRequest(
                plan_id="   ",
                spec_index=0,
                spec_data={},
                github_owner="owner",
                github_repo="repo",
            )
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("plan_id",) and "whitespace" in str(error["msg"]).lower()
            for error in errors
        )

    def test_github_owner_whitespace_only_raises_validation_error(self) -> None:
        """Test that whitespace-only github_owner raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileRequest(
                plan_id="plan-123",
                spec_index=0,
                spec_data={},
                github_owner="  \t  ",
                github_repo="repo",
            )
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("github_owner",) and "whitespace" in str(error["msg"]).lower()
            for error in errors
        )

    def test_github_repo_whitespace_only_raises_validation_error(self) -> None:
        """Test that whitespace-only github_repo raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileRequest(
                plan_id="plan-123",
                spec_index=0,
                spec_data={},
                github_owner="owner",
                github_repo="  \n  ",
            )
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("github_repo",) and "whitespace" in str(error["msg"]).lower()
            for error in errors
        )

    def test_github_owner_empty_string_raises_validation_error(self) -> None:
        """Test that empty github_owner raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileRequest(
                plan_id="plan-123",
                spec_index=0,
                spec_data={},
                github_owner="",
                github_repo="repo",
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("github_owner",) for error in errors)

    def test_github_repo_empty_string_raises_validation_error(self) -> None:
        """Test that empty github_repo raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileRequest(
                plan_id="plan-123",
                spec_index=0,
                spec_data={},
                github_owner="owner",
                github_repo="",
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("github_repo",) for error in errors)

    def test_missing_required_field_raises_validation_error(self) -> None:
        """Test that missing required fields raise validation errors."""
        with pytest.raises(ValidationError) as exc_info:
            CompileRequest(
                plan_id="plan-123",
                spec_index=0,
                # Missing spec_data, github_owner, github_repo
            )
        errors = exc_info.value.errors()
        assert len(errors) >= 3

    def test_spec_data_empty_dict_is_valid(self) -> None:
        """Test that empty dict spec_data is valid."""
        request = CompileRequest(
            plan_id="plan-123",
            spec_index=0,
            spec_data={},
            github_owner="owner",
            github_repo="repo",
        )
        assert request.spec_data == {}

    def test_spec_data_empty_list_is_valid(self) -> None:
        """Test that empty list spec_data is valid."""
        request = CompileRequest(
            plan_id="plan-123",
            spec_index=0,
            spec_data=[],
            github_owner="owner",
            github_repo="repo",
        )
        assert request.spec_data == []

    def test_spec_data_complex_nested_structure(self) -> None:
        """Test spec_data with complex nested structure."""
        complex_data = {
            "level1": {
                "level2": [
                    {"item": 1, "data": [1, 2, 3]},
                    {"item": 2, "data": {"nested": True}},
                ],
                "metadata": {"version": "1.0", "tags": ["a", "b", "c"]},
            }
        }
        request = CompileRequest(
            plan_id="plan-complex",
            spec_index=10,
            spec_data=complex_data,
            github_owner="complex-owner",
            github_repo="complex-repo",
        )
        assert request.spec_data == complex_data

    def test_model_serialization(self) -> None:
        """Test that model can be serialized to dict."""
        request = CompileRequest(
            plan_id="plan-123",
            spec_index=2,
            spec_data={"test": "data"},
            github_owner="owner",
            github_repo="repo",
        )
        data = request.model_dump()
        assert data == {
            "plan_id": "plan-123",
            "spec_index": 2,
            "spec_data": {"test": "data"},
            "github_owner": "owner",
            "github_repo": "repo",
        }

    def test_model_deserialization_from_json(self) -> None:
        """Test that model can be deserialized from JSON."""
        json_str = """
        {
            "plan_id": "plan-json",
            "spec_index": 3,
            "spec_data": {"from": "json"},
            "github_owner": "json-owner",
            "github_repo": "json-repo"
        }
        """
        request = CompileRequest.model_validate_json(json_str)
        assert request.plan_id == "plan-json"
        assert request.spec_index == 3
        assert request.spec_data == {"from": "json"}


class TestCompileResponse:
    """Tests for CompileResponse model."""

    def test_valid_response_with_accepted_status(self) -> None:
        """Test valid response with accepted status."""
        response = CompileResponse(
            request_id="req-123",
            plan_id="plan-123",
            spec_index=0,
            status="accepted",
            message="Request accepted for processing",
        )
        assert response.request_id == "req-123"
        assert response.plan_id == "plan-123"
        assert response.spec_index == 0
        assert response.status == "accepted"
        assert response.message == "Request accepted for processing"

    def test_valid_response_with_failed_status(self) -> None:
        """Test valid response with failed status."""
        response = CompileResponse(
            request_id="req-456",
            plan_id="plan-456",
            spec_index=5,
            status="failed",
            message="Validation failed",
        )
        assert response.status == "failed"
        assert response.message == "Validation failed"

    def test_response_without_message_defaults_to_none(self) -> None:
        """Test that message field defaults to None when not provided."""
        response = CompileResponse(
            request_id="req-789",
            plan_id="plan-789",
            spec_index=1,
            status="accepted",
        )
        assert response.message is None

    def test_invalid_status_raises_validation_error(self) -> None:
        """Test that invalid status value raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileResponse(
                request_id="req-123",
                plan_id="plan-123",
                spec_index=0,
                status="pending",  # Not in allowed values
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("status",) for error in errors)

    def test_missing_required_fields_raises_validation_error(self) -> None:
        """Test that missing required fields raise validation errors."""
        with pytest.raises(ValidationError) as exc_info:
            CompileResponse(
                request_id="req-123",
                # Missing plan_id, spec_index, status
            )
        errors = exc_info.value.errors()
        assert len(errors) >= 3

    def test_model_serialization(self) -> None:
        """Test that model can be serialized to dict."""
        response = CompileResponse(
            request_id="req-serialize",
            plan_id="plan-serialize",
            spec_index=7,
            status="accepted",
            message="Test message",
        )
        data = response.model_dump()
        assert data == {
            "request_id": "req-serialize",
            "plan_id": "plan-serialize",
            "spec_index": 7,
            "status": "accepted",
            "message": "Test message",
        }

    def test_model_serialization_without_message(self) -> None:
        """Test serialization when message is None."""
        response = CompileResponse(
            request_id="req-no-msg",
            plan_id="plan-no-msg",
            spec_index=0,
            status="failed",
        )
        data = response.model_dump()
        assert data["message"] is None

    def test_model_deserialization_from_json(self) -> None:
        """Test that model can be deserialized from JSON."""
        json_str = """
        {
            "request_id": "req-json",
            "plan_id": "plan-json",
            "spec_index": 2,
            "status": "failed",
            "message": "Error occurred"
        }
        """
        response = CompileResponse.model_validate_json(json_str)
        assert response.request_id == "req-json"
        assert response.status == "failed"
        assert response.message == "Error occurred"

    def test_status_enum_only_allows_accepted_and_failed(self) -> None:
        """Test that status field only accepts 'accepted' or 'failed'."""
        # Test accepted
        response1 = CompileResponse(
            request_id="req-1",
            plan_id="plan-1",
            spec_index=0,
            status="accepted",
        )
        assert response1.status == "accepted"

        # Test failed
        response2 = CompileResponse(
            request_id="req-2",
            plan_id="plan-2",
            spec_index=0,
            status="failed",
        )
        assert response2.status == "failed"

        # Test invalid values
        for invalid_status in ["success", "error", "processing", "queued"]:
            with pytest.raises(ValidationError):
                CompileResponse(
                    request_id="req-invalid",
                    plan_id="plan-invalid",
                    spec_index=0,
                    status=invalid_status,
                )
