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
Compile API request and response models.

Defines the canonical external API contract for the compile endpoint.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class CompileSpec(BaseModel):
    """
    Specification data model containing the structured spec contract.

    This model defines the six required fields that make up a specification,
    providing clear documentation and validation for the compile endpoint.

    Attributes:
        purpose: A concise statement of what this spec aims to achieve
        vision: The desired end state or outcome after implementation
        must: List of mandatory requirements that must be satisfied
        dont: List of constraints or things that must be avoided
        nice: List of optional enhancements that would be beneficial but not required
        assumptions: List of assumptions or preconditions for this spec
    """

    purpose: str = Field(
        ...,
        description="A concise statement of what this spec aims to achieve",
        min_length=1,
    )
    vision: str = Field(
        ...,
        description="The desired end state or outcome after implementation",
        min_length=1,
    )
    must: list[str] = Field(
        ...,
        description="List of mandatory requirements that must be satisfied",
    )
    dont: list[str] = Field(
        ...,
        description="List of constraints or things that must be avoided",
    )
    nice: list[str] = Field(
        ...,
        description="List of optional enhancements that would be beneficial but not required",
    )
    assumptions: list[str] = Field(
        ...,
        description="List of assumptions or preconditions for this spec",
    )

    @field_validator("purpose", "vision")
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


class CompileRequest(BaseModel):
    """
    Request model for the compile API endpoint.

    This represents the external API contract for compiling a specification.
    All fields are validated to ensure data integrity before processing.

    Attributes:
        plan_id: Non-empty identifier for the plan
        spec_index: Zero-based index of the specification (must be >= 0)
        spec: Structured specification containing purpose, vision, requirements, and constraints
        github_owner: Non-empty GitHub repository owner (user or organization)
        github_repo: Non-empty GitHub repository name
    """

    plan_id: str = Field(
        ...,
        description="Plan identifier",
        min_length=1,
    )
    spec_index: int = Field(
        ...,
        description="Specification index (must be >= 0)",
        ge=0,
    )
    spec: CompileSpec = Field(
        ...,
        description="Structured specification containing purpose, vision, requirements, and constraints",
    )
    github_owner: str = Field(
        ...,
        description="GitHub repository owner",
        min_length=1,
    )
    github_repo: str = Field(
        ...,
        description="GitHub repository name",
        min_length=1,
    )

    @field_validator("plan_id", "github_owner", "github_repo")
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


class CompileResponse(BaseModel):
    """
    Response model for the compile API endpoint.

    This represents the external API contract for the compile response.

    Attributes:
        request_id: Unique identifier for this request (UUID format)
        plan_id: Plan identifier echoed from the request
        spec_index: Specification index echoed from the request
        status: Processing status (accepted or failed)
        message: Optional message providing additional context
    """

    request_id: str = Field(
        ...,
        description="Unique request identifier",
    )
    plan_id: str = Field(
        ...,
        description="Plan identifier",
    )
    spec_index: int = Field(
        ...,
        description="Specification index",
    )
    status: Literal["accepted", "failed"] = Field(
        ...,
        description="Processing status",
    )
    message: str | None = Field(
        default=None,
        description="Optional status message",
    )
