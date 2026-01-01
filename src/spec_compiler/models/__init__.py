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
Models package for spec-compiler service.

Exports compile API contract models and LLM envelope models.
"""

import uuid
from typing import Any, Literal

from spec_compiler.models.compile import CompileRequest, CompileResponse
from spec_compiler.models.llm import (
    LlmRequestEnvelope,
    LlmResponseEnvelope,
    RepoContextPayload,
    SystemPromptConfig,
)

__all__ = [
    "CompileRequest",
    "CompileResponse",
    "SystemPromptConfig",
    "RepoContextPayload",
    "LlmRequestEnvelope",
    "LlmResponseEnvelope",
    "generate_request_id",
    "create_llm_response_stub",
]


def generate_request_id() -> str:
    """
    Generate a unique request ID using UUID4.

    Returns:
        String representation of a UUID4
    """
    return str(uuid.uuid4())


def create_llm_response_stub(
    request_id: str,
    status: Literal["success", "error", "pending", "timeout", "rate_limited"] = "pending",
    content: str = "",
    metadata: dict[str, Any] | None = None,
) -> LlmResponseEnvelope:
    """
    Create a placeholder LLM response envelope for testing/typing.

    Args:
        request_id: The request identifier
        status: Response status (default: "pending")
        content: Response content (default: "")
        metadata: Optional metadata dict (default: empty dict)

    Returns:
        LlmResponseEnvelope instance
    """
    return LlmResponseEnvelope(
        request_id=request_id,
        status=status,
        content=content,
        metadata=metadata if metadata is not None else {},
    )
