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
LLM envelope models and configurations.

Skeletal models for future LLM integration. These are used for typing
and structural placeholders but not yet connected to actual LLM services.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class SystemPromptConfig(BaseModel):
    """
    Configuration for system prompts sent to LLMs.

    This is a skeletal model for future LLM integration.

    Attributes:
        template: The system prompt template
        variables: Variables to be interpolated into the template
        max_tokens: Maximum tokens for the response
    """

    template: str = Field(
        default="",
        description="System prompt template",
    )
    variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Variables for template interpolation",
    )
    max_tokens: int = Field(
        default=4096,
        description="Maximum tokens for response",
        gt=0,
    )


class RepoContextPayload(BaseModel):
    """
    Repository context payload for LLM requests.

    Contains structured information about the repository that can be
    included in LLM prompts for context.

    Attributes:
        tree: List of file tree entries (path, type, etc.)
        dependencies: List of dependency entries (name, version, etc.)
        file_summaries: List of file summary entries (path, summary, etc.)
    """

    tree: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Repository file tree structure",
    )
    dependencies: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Repository dependencies",
    )
    file_summaries: list[dict[str, Any]] = Field(
        default_factory=list,
        description="File summaries for context",
    )


class LlmRequestEnvelope(BaseModel):
    """
    Envelope for LLM API requests.

    Wraps all data needed to make an LLM API call. This is a skeletal
    model for future implementation.

    Attributes:
        request_id: Unique identifier for request tracking
        model: LLM model identifier (e.g., "gpt-5.1", "claude-sonnet-4.5")
        system_prompt: System prompt configuration
        user_prompt: User prompt text
        repo_context: Optional repository context
        metadata: Additional metadata for logging/tracking
    """

    request_id: str = Field(
        ...,
        description="Unique request identifier",
    )
    model: str = Field(
        default="gpt-5.1",
        description="LLM model identifier",
    )
    system_prompt: SystemPromptConfig = Field(
        default_factory=SystemPromptConfig,
        description="System prompt configuration",
    )
    user_prompt: str = Field(
        default="",
        description="User prompt text",
    )
    repo_context: RepoContextPayload | None = Field(
        default=None,
        description="Optional repository context",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )


class LlmResponseEnvelope(BaseModel):
    """
    Envelope for LLM API responses.

    Wraps the response from an LLM API call. This is a skeletal model
    for future implementation.

    Attributes:
        request_id: Request identifier for correlation
        status: Response status (e.g., "success", "error", "pending")
        content: Response content from the LLM
        model: Model that generated the response
        usage: Token usage information
        metadata: Additional metadata
    """

    request_id: str = Field(
        ...,
        description="Request identifier for correlation",
    )
    status: Literal["success", "error", "pending", "timeout", "rate_limited"] = Field(
        default="pending",
        description="Response status",
    )
    content: str = Field(
        default="",
        description="Response content from LLM",
    )
    model: str | None = Field(
        default=None,
        description="Model that generated the response",
    )
    usage: dict[str, int] | None = Field(
        default=None,
        description="Token usage information",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata",
    )
