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
Plan status message model for Pub/Sub publishing.

Defines the PlanStatusMessage model that conforms to the schema documented
in plan-scheduler.openapi.json for publishing plan status updates.
"""

import json
import re
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Constants for security limits
MAX_ERROR_MESSAGE_LENGTH = 10000  # Max length for error_message to prevent oversized payloads


class PlanStatusMessage(BaseModel):
    """
    Message model for plan status updates published to Pub/Sub.

    This model conforms to the PlanStatusMessage schema defined in
    plan-scheduler.openapi.json and is used by spec-compiler to publish
    status events consumed by plan-scheduler.

    Attributes:
        plan_id: Unique identifier for the plan execution
        spec_index: Zero-based index of the spec within the plan
        status: Current status of the spec execution (in_progress, succeeded, failed)
        request_id: Request correlation ID for tracing
        timestamp: ISO8601 timestamp when the status update occurred
        error_code: Optional error code when status is 'failed'
        error_message: Optional error message providing details when status is 'failed'
    """

    plan_id: str = Field(
        ...,
        description="Unique identifier for the plan execution",
        min_length=1,
    )
    spec_index: int = Field(
        ...,
        description="Zero-based index of the spec within the plan",
        ge=0,
    )
    status: Literal["in_progress", "succeeded", "failed"] = Field(
        ...,
        description="Current status of the spec execution",
    )
    request_id: str = Field(
        ...,
        description="Request correlation ID for tracing",
        min_length=1,
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO8601 timestamp when the status update occurred",
    )
    error_code: str | None = Field(
        default=None,
        description="Optional error code when status is 'failed'",
    )
    error_message: str | None = Field(
        default=None,
        description="Optional error message providing details when status is 'failed'",
    )

    @field_validator("plan_id", "request_id")
    @classmethod
    def validate_non_whitespace(cls, v: str) -> str:
        """
        Validate that string fields are not whitespace-only.

        Args:
            v: String value to validate

        Returns:
            The validated string value

        Raises:
            ValueError: If the string is whitespace-only
        """
        if not v or not v.strip():
            raise ValueError("Field cannot be empty or whitespace-only")
        return v

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        """
        Validate that timestamp is a valid ISO8601 format.

        Args:
            v: Timestamp string to validate

        Returns:
            The validated timestamp string

        Raises:
            ValueError: If timestamp is not valid ISO8601 format
        """
        try:
            # Attempt to parse to ensure it's valid ISO8601
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except (ValueError, AttributeError) as e:
            raise ValueError(f"timestamp must be a valid ISO8601 format, got: {v}") from e
        return v

    @field_validator("error_message")
    @classmethod
    def validate_error_message(cls, v: str | None) -> str | None:
        """
        Validate and sanitize error_message to prevent oversized payloads.

        Truncates messages exceeding MAX_ERROR_MESSAGE_LENGTH and strips
        potential secrets or sensitive patterns.

        Args:
            v: Error message to validate

        Returns:
            The validated and sanitized error message

        Raises:
            ValueError: If error_message is whitespace-only when present
        """
        if v is None:
            return v

        # Check for whitespace-only strings
        if not v.strip():
            raise ValueError("error_message cannot be whitespace-only when present")

        # Truncate if too long
        if len(v) > MAX_ERROR_MESSAGE_LENGTH:
            v = v[:MAX_ERROR_MESSAGE_LENGTH] + "... (truncated)"

        # Basic sanitization: remove potential API keys or tokens
        # Pattern: strings that look like API keys (long alphanumeric strings)
        # This is a basic approach; more sophisticated sanitization can be added
        sanitized = re.sub(
            r'\b[A-Za-z0-9_-]{32,}\b',
            '[REDACTED]',
            v
        )

        return sanitized

    def to_json_dict(self) -> dict[str, str | int | None]:
        """
        Serialize the message to a JSON-compatible dictionary.

        This method preserves field names exactly as defined in the schema
        without any renaming or transformation.

        Returns:
            Dictionary representation of the message suitable for JSON serialization
        """
        return self.model_dump(mode="json", exclude_none=False)

    def to_json_bytes(self) -> bytes:
        """
        Serialize the message to JSON bytes for Pub/Sub publishing.

        Returns:
            UTF-8 encoded JSON bytes
        """
        return json.dumps(self.to_json_dict()).encode("utf-8")
