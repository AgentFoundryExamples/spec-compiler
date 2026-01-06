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

from spec_compiler.models.compile import CompileRequest, CompileResponse, CompileSpec


class TestCompileSpec:
    """Tests for CompileSpec model."""

    def test_valid_spec_with_all_fields(self) -> None:
        """Test valid CompileSpec with all required fields."""
        spec = CompileSpec(
            purpose="Add user authentication",
            vision="Users can securely log in and manage their accounts",
            must=["Support OAuth2", "Store passwords securely"],
            dont=["Store passwords in plain text", "Use deprecated auth libraries"],
            nice=["Support social login", "Add two-factor authentication"],
            assumptions=["Users have email addresses", "HTTPS is enabled"],
        )
        assert spec.purpose == "Add user authentication"
        assert spec.vision == "Users can securely log in and manage their accounts"
        assert len(spec.must) == 2
        assert len(spec.dont) == 2
        assert len(spec.nice) == 2
        assert len(spec.assumptions) == 2

    def test_valid_spec_with_empty_lists(self) -> None:
        """Test that empty lists are valid for list fields."""
        spec = CompileSpec(
            purpose="Simple change",
            vision="Quick fix",
            must=[],
            dont=[],
            nice=[],
            assumptions=[],
        )
        assert spec.must == []
        assert spec.dont == []
        assert spec.nice == []
        assert spec.assumptions == []

    def test_missing_purpose_raises_validation_error(self) -> None:
        """Test that missing purpose field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                vision="Some vision",
                must=[],
                dont=[],
                nice=[],
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("purpose",) for error in errors)

    def test_missing_vision_raises_validation_error(self) -> None:
        """Test that missing vision field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="Some purpose",
                must=[],
                dont=[],
                nice=[],
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("vision",) for error in errors)

    def test_missing_must_raises_validation_error(self) -> None:
        """Test that missing must field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="Some purpose",
                vision="Some vision",
                dont=[],
                nice=[],
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("must",) for error in errors)

    def test_missing_dont_raises_validation_error(self) -> None:
        """Test that missing dont field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="Some purpose",
                vision="Some vision",
                must=[],
                nice=[],
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("dont",) for error in errors)

    def test_missing_nice_raises_validation_error(self) -> None:
        """Test that missing nice field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="Some purpose",
                vision="Some vision",
                must=[],
                dont=[],
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("nice",) for error in errors)

    def test_missing_assumptions_raises_validation_error(self) -> None:
        """Test that missing assumptions field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="Some purpose",
                vision="Some vision",
                must=[],
                dont=[],
                nice=[],
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("assumptions",) for error in errors)

    def test_empty_purpose_raises_validation_error(self) -> None:
        """Test that empty purpose string raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="",
                vision="Some vision",
                must=[],
                dont=[],
                nice=[],
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("purpose",) for error in errors)

    def test_empty_vision_raises_validation_error(self) -> None:
        """Test that empty vision string raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="Some purpose",
                vision="",
                must=[],
                dont=[],
                nice=[],
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("vision",) for error in errors)

    def test_whitespace_only_purpose_raises_validation_error(self) -> None:
        """Test that whitespace-only purpose raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="   ",
                vision="Some vision",
                must=[],
                dont=[],
                nice=[],
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("purpose",) and "whitespace" in str(error["msg"]).lower()
            for error in errors
        )

    def test_whitespace_only_vision_raises_validation_error(self) -> None:
        """Test that whitespace-only vision raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="Some purpose",
                vision="  \t  ",
                must=[],
                dont=[],
                nice=[],
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("vision",) and "whitespace" in str(error["msg"]).lower()
            for error in errors
        )

    def test_must_as_string_raises_validation_error(self) -> None:
        """Test that providing must as string instead of list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="Some purpose",
                vision="Some vision",
                must="should be a list",
                dont=[],
                nice=[],
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("must",) for error in errors)

    def test_dont_as_string_raises_validation_error(self) -> None:
        """Test that providing dont as string instead of list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="Some purpose",
                vision="Some vision",
                must=[],
                dont="should be a list",
                nice=[],
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("dont",) for error in errors)

    def test_nice_as_string_raises_validation_error(self) -> None:
        """Test that providing nice as string instead of list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="Some purpose",
                vision="Some vision",
                must=[],
                dont=[],
                nice="should be a list",
                assumptions=[],
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("nice",) for error in errors)

    def test_assumptions_as_string_raises_validation_error(self) -> None:
        """Test that providing assumptions as string instead of list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileSpec(
                purpose="Some purpose",
                vision="Some vision",
                must=[],
                dont=[],
                nice=[],
                assumptions="should be a list",
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("assumptions",) for error in errors)

    def test_model_serialization(self) -> None:
        """Test that CompileSpec can be serialized to dict."""
        spec = CompileSpec(
            purpose="Test purpose",
            vision="Test vision",
            must=["req1", "req2"],
            dont=["avoid1"],
            nice=["nice1"],
            assumptions=["assume1"],
        )
        data = spec.model_dump()
        assert data == {
            "purpose": "Test purpose",
            "vision": "Test vision",
            "must": ["req1", "req2"],
            "dont": ["avoid1"],
            "nice": ["nice1"],
            "assumptions": ["assume1"],
        }

    def test_model_deserialization_from_json(self) -> None:
        """Test that CompileSpec can be deserialized from JSON."""
        json_str = """
        {
            "purpose": "Test purpose",
            "vision": "Test vision",
            "must": ["req1"],
            "dont": ["avoid1"],
            "nice": [],
            "assumptions": ["assume1"]
        }
        """
        spec = CompileSpec.model_validate_json(json_str)
        assert spec.purpose == "Test purpose"
        assert spec.vision == "Test vision"
        assert spec.must == ["req1"]
        assert spec.dont == ["avoid1"]
        assert spec.nice == []
        assert spec.assumptions == ["assume1"]


class TestCompileRequest:
    """Tests for CompileRequest model."""

    def test_valid_request_with_spec(self) -> None:
        """Test valid request with CompileSpec."""
        spec = CompileSpec(
            purpose="Add authentication",
            vision="Secure user login",
            must=["OAuth2 support"],
            dont=["Plain text passwords"],
            nice=["Social login"],
            assumptions=["HTTPS enabled"],
        )
        request = CompileRequest(
            plan_id="plan-123",
            spec_index=0,
            spec=spec,
            github_owner="example-owner",
            github_repo="example-repo",
        )
        assert request.plan_id == "plan-123"
        assert request.spec_index == 0
        assert request.spec.purpose == "Add authentication"
        assert request.github_owner == "example-owner"
        assert request.github_repo == "example-repo"

    def test_valid_request_with_inline_spec(self) -> None:
        """Test valid request with inline spec dict."""
        request = CompileRequest(
            plan_id="plan-456",
            spec_index=5,
            spec={
                "purpose": "Fix bug",
                "vision": "Bug is resolved",
                "must": ["Fix crash"],
                "dont": ["Break existing features"],
                "nice": ["Add tests"],
                "assumptions": ["Bug is reproducible"],
            },
            github_owner="test-org",
            github_repo="test-repo",
        )
        assert request.spec_index == 5
        assert request.spec.purpose == "Fix bug"
        assert request.spec.must == ["Fix crash"]

    def test_spec_index_zero_is_valid(self) -> None:
        """Test that spec_index can be zero."""
        request = CompileRequest(
            plan_id="plan-0",
            spec_index=0,
            spec={
                "purpose": "Test",
                "vision": "Test",
                "must": [],
                "dont": [],
                "nice": [],
                "assumptions": [],
            },
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
                spec={
                    "purpose": "Test",
                    "vision": "Test",
                    "must": [],
                    "dont": [],
                    "nice": [],
                    "assumptions": [],
                },
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
                spec={
                    "purpose": "Test",
                    "vision": "Test",
                    "must": [],
                    "dont": [],
                    "nice": [],
                    "assumptions": [],
                },
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
                spec={
                    "purpose": "Test",
                    "vision": "Test",
                    "must": [],
                    "dont": [],
                    "nice": [],
                    "assumptions": [],
                },
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
                spec={
                    "purpose": "Test",
                    "vision": "Test",
                    "must": [],
                    "dont": [],
                    "nice": [],
                    "assumptions": [],
                },
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
                spec={
                    "purpose": "Test",
                    "vision": "Test",
                    "must": [],
                    "dont": [],
                    "nice": [],
                    "assumptions": [],
                },
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
                spec={
                    "purpose": "Test",
                    "vision": "Test",
                    "must": [],
                    "dont": [],
                    "nice": [],
                    "assumptions": [],
                },
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
                spec={
                    "purpose": "Test",
                    "vision": "Test",
                    "must": [],
                    "dont": [],
                    "nice": [],
                    "assumptions": [],
                },
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
                # Missing spec, github_owner, github_repo
            )
        errors = exc_info.value.errors()
        assert len(errors) >= 3

    def test_spec_with_empty_lists_is_valid(self) -> None:
        """Test that spec with empty lists is valid."""
        request = CompileRequest(
            plan_id="plan-123",
            spec_index=0,
            spec={
                "purpose": "Test",
                "vision": "Test",
                "must": [],
                "dont": [],
                "nice": [],
                "assumptions": [],
            },
            github_owner="owner",
            github_repo="repo",
        )
        assert request.spec.must == []
        assert request.spec.dont == []
        assert request.spec.nice == []
        assert request.spec.assumptions == []

    def test_spec_missing_field_raises_validation_error(self) -> None:
        """Test that missing spec field raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            CompileRequest(
                plan_id="plan-123",
                spec_index=0,
                spec={
                    "purpose": "Test",
                    "vision": "Test",
                    # Missing must, dont, nice, assumptions
                },
                github_owner="owner",
                github_repo="repo",
            )
        errors = exc_info.value.errors()
        # Should have errors for the missing fields in spec
        assert any("spec" in str(error["loc"]) for error in errors)

    def test_spec_with_populated_lists(self) -> None:
        """Test spec with populated list fields."""
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
            spec={
                "purpose": "Complex spec",
                "vision": "Handle complex scenarios",
                "must": ["requirement 1", "requirement 2", "requirement 3"],
                "dont": ["avoid pattern 1", "avoid pattern 2"],
                "nice": ["nice to have 1"],
                "assumptions": ["assumption 1", "assumption 2"],
            },
            github_owner="complex-owner",
            github_repo="complex-repo",
        )
        assert len(request.spec.must) == 3
        assert len(request.spec.dont) == 2
        assert len(request.spec.nice) == 1
        assert len(request.spec.assumptions) == 2

    def test_model_serialization(self) -> None:
        """Test that model can be serialized to dict."""
        request = CompileRequest(
            plan_id="plan-123",
            spec_index=2,
            spec={
                "purpose": "Test",
                "vision": "Test vision",
                "must": ["req1"],
                "dont": [],
                "nice": [],
                "assumptions": [],
            },
            github_owner="owner",
            github_repo="repo",
        )
        data = request.model_dump()
        assert data["plan_id"] == "plan-123"
        assert data["spec_index"] == 2
        assert data["spec"]["purpose"] == "Test"
        assert data["github_owner"] == "owner"
        assert data["github_repo"] == "repo"

    def test_model_deserialization_from_json(self) -> None:
        """Test that model can be deserialized from JSON."""
        json_str = """
        {
            "plan_id": "plan-json",
            "spec_index": 3,
            "spec": {
                "purpose": "Test purpose",
                "vision": "Test vision",
                "must": ["req1"],
                "dont": [],
                "nice": [],
                "assumptions": []
            },
            "github_owner": "json-owner",
            "github_repo": "json-repo"
        }
        """
        request = CompileRequest.model_validate_json(json_str)
        assert request.plan_id == "plan-json"
        assert request.spec_index == 3
        assert request.spec.purpose == "Test purpose"


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
