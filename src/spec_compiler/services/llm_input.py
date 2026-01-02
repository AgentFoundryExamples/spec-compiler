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
combining system prompts, repository context, and specification data into
a deterministic format suitable for the Responses API.

TODO: Future enhancement - Add optional config parameter to redact or truncate
      oversized sections when instructed by configuration. This would help
      manage token limits while preserving testability with fixtures.
"""

import json
from typing import Any


class LlmInputComposer:
    """
    Compose structured input content for LLM requests.

    This class builds deterministic labeled JSON content that includes all
    necessary context for LLM-based spec compilation: system prompt, repository
    tree, dependencies, file summaries, and the request specification data.
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
    def compose_user_content(
        system_prompt: str,
        tree_json: dict[str, Any] | list[Any],
        dependencies_json: dict[str, Any] | list[Any],
        file_summaries_json: dict[str, Any] | list[Any],
        spec_data: dict[str, Any] | list[Any],
    ) -> str:
        """
        Compose structured user content for LLM requests.

        Builds a deterministic labeled JSON structure containing all input
        sections with clear delimiters. Each section is included as a labeled
        JSON block.

        Args:
            system_prompt: System prompt text describing the task
            tree_json: Repository file tree structure
            dependencies_json: Repository dependencies
            file_summaries_json: File summaries for context
            spec_data: Request specification data to be compiled

        Returns:
            String containing the composed content with labeled sections

        Raises:
            ValueError: If any required input is missing or empty
        """
        # Validate required inputs
        LlmInputComposer._validate_inputs(
            system_prompt, tree_json, dependencies_json, file_summaries_json, spec_data
        )

        # Build the composed content with labeled sections
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
    format_type: str = "string",
) -> str | dict[str, Any]:
    """
    Convenience function to compose LLM request payload.

    This is a wrapper around LlmInputComposer methods for easier usage.

    Args:
        system_prompt: System prompt text describing the task
        tree_json: Repository file tree structure
        dependencies_json: Repository dependencies
        file_summaries_json: File summaries for context
        spec_data: Request specification data to be compiled
        format_type: Output format ("string" or "structured")

    Returns:
        Composed content as string or structured dict based on format_type

    Raises:
        ValueError: If inputs are invalid or format_type is unknown
    """
    composer = LlmInputComposer()

    if format_type == "string":
        return composer.compose_user_content(
            system_prompt,
            tree_json,
            dependencies_json,
            file_summaries_json,
            spec_data,
        )
    elif format_type == "structured":
        return composer.compose_structured_content(
            system_prompt,
            tree_json,
            dependencies_json,
            file_summaries_json,
            spec_data,
        )
    else:
        raise ValueError(f"Unknown format_type: {format_type}. Use 'string' or 'structured'")
