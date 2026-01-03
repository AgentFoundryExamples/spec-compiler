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
LLM input composition utilities.

Provides functions to compose structured user content for LLM requests,
separating system prompts from user messages and wrapping repository JSON
artifacts in labeled fenced blocks for clarity.

The key change from previous implementation:
- System prompts are kept separate and never mixed into user content
- Repository JSON artifacts are embedded as complete file bodies in ```json fences
- SDK clients receive (system_prompt, user_content) separately

TODO: Future enhancement - Add optional config parameter to redact or truncate
      oversized sections when instructed by configuration. This would help
      manage token limits while preserving testability with fixtures.
"""

import json
from typing import Any, NamedTuple


class LlmInputStructure(NamedTuple):
    """
    Structure for LLM input separating system prompt from user messages.

    Attributes:
        system_prompt: System prompt to be sent via SDK system parameter
        user_content: User message content with repo context and spec data
    """

    system_prompt: str
    user_content: str


class LlmInputComposer:
    """
    Compose structured input content for LLM requests.

    This class builds deterministic labeled content that separates system prompts
    from user messages and embeds repository JSON artifacts in labeled fenced
    blocks for LLM-based spec compilation.

    Key principles:
    - System prompts are returned separately, never embedded in user content
    - Repository artifacts (tree, dependencies, file summaries) are wrapped in
      labeled ```json fenced blocks with their complete content
    - Deterministic ordering ensures reproducible prompts across runs
    """

    @staticmethod
    def _validate_inputs(
        system_prompt: str,
        tree_json: dict[str, Any] | list[Any],
        dependencies_json: dict[str, Any] | list[Any],
        file_summaries_json: dict[str, Any] | list[Any],
        spec_data: dict[str, Any] | list[Any],
    ) -> None:
        """
        Validate required inputs for composition methods.

        Args:
            system_prompt: System prompt text describing the task
            tree_json: Repository file tree structure
            dependencies_json: Repository dependencies
            file_summaries_json: File summaries for context
            spec_data: Request specification data to be compiled

        Raises:
            ValueError: If any required input is missing or empty
        """
        if not system_prompt or not system_prompt.strip():
            raise ValueError("system_prompt cannot be empty or whitespace-only")

        if tree_json is None:
            raise ValueError("tree_json cannot be None")

        if dependencies_json is None:
            raise ValueError("dependencies_json cannot be None")

        if file_summaries_json is None:
            raise ValueError("file_summaries_json cannot be None")

        if spec_data is None:
            raise ValueError("spec_data cannot be None")

    @staticmethod
    def _compose_user_content_only(
        tree_json: dict[str, Any] | list[Any],
        dependencies_json: dict[str, Any] | list[Any],
        file_summaries_json: dict[str, Any] | list[Any],
        spec_data: dict[str, Any] | list[Any],
    ) -> str:
        """
        Compose user content WITHOUT system prompt (internal method).

        Embeds repository JSON artifacts in labeled ```json fenced blocks
        and includes specification data. System prompt is handled separately.

        This is an internal method used by compose_separated(). External callers
        should use compose_separated() instead.

        Args:
            tree_json: Repository file tree structure (entire JSON)
            dependencies_json: Repository dependencies (entire JSON)
            file_summaries_json: File summaries for context (entire JSON)
            spec_data: Request specification data to be compiled

        Returns:
            String containing the composed user content with fenced JSON blocks

        Raises:
            ValueError: If any required input is None
        """
        # Validate inputs (except system_prompt)
        if tree_json is None:
            raise ValueError("tree_json cannot be None")
        if dependencies_json is None:
            raise ValueError("dependencies_json cannot be None")
        if file_summaries_json is None:
            raise ValueError("file_summaries_json cannot be None")
        if spec_data is None:
            raise ValueError("spec_data cannot be None")

        # Build content with labeled JSON fenced blocks
        # Each repository artifact is wrapped in a fenced block with a clear label
        sections = [
            "=====TREE=====",
            "```json",
            json.dumps(tree_json, indent=2),
            "```",
            "",
            "=====DEPENDENCIES=====",
            "```json",
            json.dumps(dependencies_json, indent=2),
            "```",
            "",
            "=====FILE_SUMMARIES=====",
            "```json",
            json.dumps(file_summaries_json, indent=2),
            "```",
            "",
            "=====SPECIFICATION=====",
            "```json",
            json.dumps(spec_data, indent=2),
            "```",
        ]

        return "\n".join(sections)

    @staticmethod
    def compose_separated(
        system_prompt: str,
        tree_json: dict[str, Any] | list[Any],
        dependencies_json: dict[str, Any] | list[Any],
        file_summaries_json: dict[str, Any] | list[Any],
        spec_data: dict[str, Any] | list[Any],
    ) -> LlmInputStructure:
        """
        Compose LLM input with separated system prompt and user content.

        This is the NEW recommended method that returns a structured object
        with system_prompt and user_content as separate fields. Repository
        JSON artifacts are embedded verbatim in labeled ```json fenced blocks.

        SDK clients should use system_prompt for the system parameter and
        user_content for the user message parameter.

        Args:
            system_prompt: System prompt text describing the task
            tree_json: Repository file tree structure (entire JSON)
            dependencies_json: Repository dependencies (entire JSON)
            file_summaries_json: File summaries for context (entire JSON)
            spec_data: Request specification data to be compiled

        Returns:
            LlmInputStructure with separated system_prompt and user_content

        Raises:
            ValueError: If any required input is missing or empty
        """
        # Validate all inputs including system_prompt
        LlmInputComposer._validate_inputs(
            system_prompt, tree_json, dependencies_json, file_summaries_json, spec_data
        )

        # Get user content without system prompt
        user_content = LlmInputComposer._compose_user_content_only(
            tree_json, dependencies_json, file_summaries_json, spec_data
        )

        return LlmInputStructure(
            system_prompt=system_prompt.strip(),
            user_content=user_content,
        )

    @staticmethod
    def compose_user_content(
        system_prompt: str,
        tree_json: dict[str, Any] | list[Any],
        dependencies_json: dict[str, Any] | list[Any],
        file_summaries_json: dict[str, Any] | list[Any],
        spec_data: dict[str, Any] | list[Any],
    ) -> str:
        """
        Compose user content with system prompt (DEPRECATED - for backward compatibility).

        This method is kept for backward compatibility with existing code but is
        DEPRECATED. New code should use compose_separated() instead to avoid
        duplicating the system prompt in user content.

        This old approach embeds the system prompt in the user content, which
        causes duplication when SDK clients also accept a system parameter.

        Args:
            system_prompt: System prompt text describing the task
            tree_json: Repository file tree structure
            dependencies_json: Repository dependencies
            file_summaries_json: File summaries for context
            spec_data: Request specification data to be compiled

        Returns:
            String containing the composed content with system prompt included

        Raises:
            ValueError: If any required input is missing or empty
        """
        # Validate required inputs
        LlmInputComposer._validate_inputs(
            system_prompt, tree_json, dependencies_json, file_summaries_json, spec_data
        )

        # Build the composed content with system prompt included (old format)
        sections = [
            "=== SYSTEM PROMPT ===",
            system_prompt.strip(),
            "",
            "=== REPOSITORY TREE ===",
            json.dumps(tree_json, indent=2),
            "",
            "=== DEPENDENCIES ===",
            json.dumps(dependencies_json, indent=2),
            "",
            "=== FILE SUMMARIES ===",
            json.dumps(file_summaries_json, indent=2),
            "",
            "=== SPECIFICATION DATA ===",
            json.dumps(spec_data, indent=2),
        ]

        return "\n".join(sections)

    @staticmethod
    def compose_structured_content(
        system_prompt: str,
        tree_json: dict[str, Any] | list[Any],
        dependencies_json: dict[str, Any] | list[Any],
        file_summaries_json: dict[str, Any] | list[Any],
        spec_data: dict[str, Any] | list[Any],
    ) -> dict[str, Any]:
        """
        Compose structured user content as a JSON object.

        Alternative to compose_user_content that returns a structured object
        instead of a string. This can be useful for APIs that accept structured
        content directly.

        Args:
            system_prompt: System prompt text describing the task
            tree_json: Repository file tree structure
            dependencies_json: Repository dependencies
            file_summaries_json: File summaries for context
            spec_data: Request specification data to be compiled

        Returns:
            Dictionary containing all sections as structured data

        Raises:
            ValueError: If any required input is missing or empty
        """
        # Validate required inputs
        LlmInputComposer._validate_inputs(
            system_prompt, tree_json, dependencies_json, file_summaries_json, spec_data
        )

        return {
            "system_prompt": system_prompt.strip(),
            "repository_tree": tree_json,
            "dependencies": dependencies_json,
            "file_summaries": file_summaries_json,
            "specification_data": spec_data,
        }


def compose_llm_request_payload(
    system_prompt: str,
    tree_json: dict[str, Any] | list[Any],
    dependencies_json: dict[str, Any] | list[Any],
    file_summaries_json: dict[str, Any] | list[Any],
    spec_data: dict[str, Any] | list[Any],
    format_type: str = "separated",
) -> str | dict[str, Any] | LlmInputStructure:
    """
    Convenience function to compose LLM request payload.

    This is a wrapper around LlmInputComposer methods for easier usage.

    Args:
        system_prompt: System prompt text describing the task
        tree_json: Repository file tree structure
        dependencies_json: Repository dependencies
        file_summaries_json: File summaries for context
        spec_data: Request specification data to be compiled
        format_type: Output format:
            - "separated" (NEW, RECOMMENDED): Returns LlmInputStructure with system_prompt separate
            - "string" (DEPRECATED): Returns string with system prompt included
            - "structured": Returns dict with all sections

    Returns:
        Composed content based on format_type:
        - LlmInputStructure for "separated"
        - str for "string"
        - dict for "structured"

    Raises:
        ValueError: If inputs are invalid or format_type is unknown
    """
    composer = LlmInputComposer()

    if format_type == "separated":
        return composer.compose_separated(
            system_prompt,
            tree_json,
            dependencies_json,
            file_summaries_json,
            spec_data,
        )
    elif format_type == "string":
        return composer.compose_user_content(
            system_prompt,
            tree_json,
            dependencies_json,
            file_summaries_json,
            spec_data,
        )
    elif format_type == "structured":
        structured_content = composer.compose_structured_content(
            system_prompt,
            tree_json,
            dependencies_json,
            file_summaries_json,
            spec_data,
        )
        # Ensure we always return a dict (compose_structured_content always returns dict,
        # but this provides extra safety in case of future changes)
        return structured_content or {
            "system_prompt": system_prompt.strip(),
            "repository_tree": tree_json or {},
            "dependencies": dependencies_json or {},
            "file_summaries": file_summaries_json or {},
            "specification_data": spec_data or {},
        }
    else:
        raise ValueError(
            f"Unknown format_type: {format_type}. Use 'separated', 'string', or 'structured'"
        )
