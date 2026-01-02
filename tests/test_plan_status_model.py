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
Tests for PlanStatusMessage model.

Validates the plan status message model including field validation,
timestamp auto-population, and JSON serialization.
"""

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from spec_compiler.models.plan_status import MAX_ERROR_MESSAGE_LENGTH, PlanStatusMessage


class TestPlanStatusMessage:
    """Tests for PlanStatusMessage model."""

    def test_valid_message_in_progress(self) -> None:
        """Test valid message with in_progress status."""
        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )
        assert message.plan_id == "plan-123"
        assert message.spec_index == 0
        assert message.status == "in_progress"
        assert message.request_id == "req-456"
        assert message.timestamp is not None
        assert message.error_code is None
        assert message.error_message is None

    def test_valid_message_succeeded(self) -> None:
        """Test valid message with succeeded status."""
        message = PlanStatusMessage(
            plan_id="plan-abc",
            spec_index=5,
            status="succeeded",
            request_id="req-xyz",
        )
        assert message.status == "succeeded"

    def test_valid_message_failed_with_error(self) -> None:
        """Test valid message with failed status and error details."""
        message = PlanStatusMessage(
            plan_id="plan-def",
            spec_index=2,
            status="failed",
            request_id="req-789",
            error_code="COMPILATION_ERROR",
            error_message="LLM compilation failed: timeout exceeded",
        )
        assert message.status == "failed"
        assert message.error_code == "COMPILATION_ERROR"
        assert message.error_message == "LLM compilation failed: timeout exceeded"

    def test_timestamp_auto_populated(self) -> None:
        """Test that timestamp is auto-populated when not provided."""
        before = datetime.now(UTC).isoformat()
        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )
        after = datetime.now(UTC).isoformat()

        assert message.timestamp is not None
        assert before <= message.timestamp <= after

    def test_timestamp_custom_value(self) -> None:
        """Test that custom timestamp value is preserved."""
        custom_timestamp = "2026-01-02T18:18:33.883Z"
        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
            timestamp=custom_timestamp,
        )
        assert message.timestamp == custom_timestamp

    def test_spec_index_zero_is_valid(self) -> None:
        """Test that spec_index can be zero."""
        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )
        assert message.spec_index == 0

    def test_spec_index_negative_raises_error(self) -> None:
        """Test that negative spec_index raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            PlanStatusMessage(
                plan_id="plan-123",
                spec_index=-1,
                status="in_progress",
                request_id="req-456",
            )
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("spec_index",) and error["type"] == "greater_than_equal"
            for error in errors
        )

    def test_plan_id_empty_raises_error(self) -> None:
        """Test that empty plan_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            PlanStatusMessage(
                plan_id="",
                spec_index=0,
                status="in_progress",
                request_id="req-456",
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("plan_id",) for error in errors)

    def test_plan_id_whitespace_raises_error(self) -> None:
        """Test that whitespace-only plan_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            PlanStatusMessage(
                plan_id="   ",
                spec_index=0,
                status="in_progress",
                request_id="req-456",
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("plan_id",) for error in errors)

    def test_request_id_empty_raises_error(self) -> None:
        """Test that empty request_id raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            PlanStatusMessage(
                plan_id="plan-123",
                spec_index=0,
                status="in_progress",
                request_id="",
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("request_id",) for error in errors)

    def test_status_invalid_value_raises_error(self) -> None:
        """Test that invalid status value raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            PlanStatusMessage(
                plan_id="plan-123",
                spec_index=0,
                status="invalid_status",  # type: ignore
                request_id="req-456",
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("status",) for error in errors)

    def test_timestamp_invalid_format_raises_error(self) -> None:
        """Test that invalid timestamp format raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            PlanStatusMessage(
                plan_id="plan-123",
                spec_index=0,
                status="in_progress",
                request_id="req-456",
                timestamp="not-a-valid-timestamp",
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("timestamp",) for error in errors)

    def test_error_message_whitespace_raises_error(self) -> None:
        """Test that whitespace-only error_message raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            PlanStatusMessage(
                plan_id="plan-123",
                spec_index=0,
                status="failed",
                request_id="req-456",
                error_message="   ",
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("error_message",) for error in errors)

    def test_error_message_truncation(self) -> None:
        """Test that oversized error_message is truncated."""
        long_message = "x" * (MAX_ERROR_MESSAGE_LENGTH + 1000)
        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="failed",
            request_id="req-456",
            error_message=long_message,
        )
        assert len(message.error_message) <= MAX_ERROR_MESSAGE_LENGTH + 20  # type: ignore
        assert message.error_message.endswith("(truncated)")  # type: ignore

    def test_error_message_secret_sanitization(self) -> None:
        """Test that potential secrets in error_message are sanitized."""
        message_with_secret = (
            "API call failed with token: sk_test_abcdef1234567890abcdef1234567890abcdef"
        )
        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="failed",
            request_id="req-456",
            error_message=message_with_secret,
        )
        assert "[REDACTED]" in message.error_message  # type: ignore
        assert "sk_test_abcdef1234567890abcdef1234567890abcdef" not in message.error_message  # type: ignore

    def test_to_json_dict(self) -> None:
        """Test JSON dictionary serialization."""
        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
            timestamp="2026-01-02T18:18:33.883Z",
        )
        json_dict = message.to_json_dict()

        assert isinstance(json_dict, dict)
        assert json_dict["plan_id"] == "plan-123"
        assert json_dict["spec_index"] == 0
        assert json_dict["status"] == "in_progress"
        assert json_dict["request_id"] == "req-456"
        assert json_dict["timestamp"] == "2026-01-02T18:18:33.883Z"
        assert json_dict["error_code"] is None
        assert json_dict["error_message"] is None

    def test_to_json_dict_with_error(self) -> None:
        """Test JSON dictionary serialization with error details."""
        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="failed",
            request_id="req-456",
            error_code="TIMEOUT",
            error_message="Request timed out",
        )
        json_dict = message.to_json_dict()

        assert json_dict["error_code"] == "TIMEOUT"
        assert json_dict["error_message"] == "Request timed out"

    def test_to_json_bytes(self) -> None:
        """Test JSON bytes serialization."""
        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="succeeded",
            request_id="req-456",
            timestamp="2026-01-02T18:18:33.883Z",
        )
        json_bytes = message.to_json_bytes()

        assert isinstance(json_bytes, bytes)
        # Verify it's valid JSON
        parsed = json.loads(json_bytes.decode("utf-8"))
        assert parsed["plan_id"] == "plan-123"
        assert parsed["status"] == "succeeded"

    def test_field_names_not_renamed(self) -> None:
        """Test that field names are preserved in JSON serialization."""
        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )
        json_dict = message.to_json_dict()

        # Verify exact field names match schema
        assert "plan_id" in json_dict
        assert "spec_index" in json_dict
        assert "status" in json_dict
        assert "request_id" in json_dict
        assert "timestamp" in json_dict
        assert "error_code" in json_dict
        assert "error_message" in json_dict

        # Ensure no camelCase or other transformations
        assert "planId" not in json_dict
        assert "specIndex" not in json_dict
        assert "requestId" not in json_dict
        assert "errorCode" not in json_dict
        assert "errorMessage" not in json_dict
