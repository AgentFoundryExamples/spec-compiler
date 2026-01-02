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
Tests for LLM input composition utilities.

Validates the composition of structured user content for LLM requests.
"""

import pytest

from spec_compiler.services.llm_input import (
    LlmInputComposer,
    compose_llm_request_payload,
)


class TestLlmInputComposer:
    """Tests for LlmInputComposer class."""

    def test_compose_user_content_success(self) -> None:
        """Test successful composition of user content."""
        composer = LlmInputComposer()

        system_prompt = "You are a helpful assistant."
        tree_json = {"files": ["file1.py", "file2.py"]}
        dependencies_json = {"dependencies": [{"name": "pytest", "version": "8.3.4"}]}
        file_summaries_json = {"summaries": [{"path": "file1.py", "summary": "Main file"}]}
        spec_data = {"spec": "value"}

        result = composer.compose_user_content(
            system_prompt,
            tree_json,
            dependencies_json,
            file_summaries_json,
            spec_data,
        )

        # Verify all sections are present
        assert "=== SYSTEM PROMPT ===" in result
        assert "You are a helpful assistant." in result
        assert "=== REPOSITORY TREE ===" in result
        assert '"files"' in result
        assert "=== DEPENDENCIES ===" in result
        assert '"pytest"' in result
        assert "=== FILE SUMMARIES ===" in result
        assert '"summaries"' in result
        assert "=== SPECIFICATION DATA ===" in result
        assert '"spec"' in result

    def test_compose_user_content_with_lists(self) -> None:
        """Test composition with list inputs instead of dicts."""
        composer = LlmInputComposer()

        system_prompt = "Process this data."
        tree_json = ["file1.py", "file2.py"]
        dependencies_json = [{"name": "lib"}]
        file_summaries_json = []
        spec_data = ["item1", "item2"]

        result = composer.compose_user_content(
            system_prompt,
            tree_json,
            dependencies_json,
            file_summaries_json,
            spec_data,
        )

        assert "=== SYSTEM PROMPT ===" in result
        assert "Process this data." in result
        assert '"file1.py"' in result
        assert '"item1"' in result

    def test_compose_user_content_empty_system_prompt(self) -> None:
        """Test that empty system prompt raises error."""
        composer = LlmInputComposer()

        with pytest.raises(ValueError, match="system_prompt cannot be empty"):
            composer.compose_user_content(
                "",
                {"tree": []},
                {"deps": []},
                {"summaries": []},
                {"spec": "data"},
            )

    def test_compose_user_content_whitespace_system_prompt(self) -> None:
        """Test that whitespace-only system prompt raises error."""
        composer = LlmInputComposer()

        with pytest.raises(ValueError, match="system_prompt cannot be empty"):
            composer.compose_user_content(
                "   ",
                {"tree": []},
                {"deps": []},
                {"summaries": []},
                {"spec": "data"},
            )

    def test_compose_user_content_none_tree_json(self) -> None:
        """Test that None tree_json raises error."""
        composer = LlmInputComposer()

        with pytest.raises(ValueError, match="tree_json cannot be None"):
            composer.compose_user_content(
                "prompt",
                None,
                {"deps": []},
                {"summaries": []},
                {"spec": "data"},
            )

    def test_compose_user_content_none_dependencies_json(self) -> None:
        """Test that None dependencies_json raises error."""
        composer = LlmInputComposer()

        with pytest.raises(ValueError, match="dependencies_json cannot be None"):
            composer.compose_user_content(
                "prompt",
                {"tree": []},
                None,
                {"summaries": []},
                {"spec": "data"},
            )

    def test_compose_user_content_none_file_summaries_json(self) -> None:
        """Test that None file_summaries_json raises error."""
        composer = LlmInputComposer()

        with pytest.raises(ValueError, match="file_summaries_json cannot be None"):
            composer.compose_user_content(
                "prompt",
                {"tree": []},
                {"deps": []},
                None,
                {"spec": "data"},
            )

    def test_compose_user_content_none_spec_data(self) -> None:
        """Test that None spec_data raises error."""
        composer = LlmInputComposer()

        with pytest.raises(ValueError, match="spec_data cannot be None"):
            composer.compose_user_content(
                "prompt",
                {"tree": []},
                {"deps": []},
                {"summaries": []},
                None,
            )

    def test_compose_user_content_empty_sections_allowed(self) -> None:
        """Test that empty dicts/lists are allowed (not None)."""
        composer = LlmInputComposer()

        result = composer.compose_user_content(
            "prompt",
            {},
            [],
            {},
            [],
        )

        assert "=== SYSTEM PROMPT ===" in result
        assert "=== REPOSITORY TREE ===" in result
        assert "{}" in result
        assert "[]" in result

    def test_compose_structured_content_success(self) -> None:
        """Test successful composition of structured content."""
        composer = LlmInputComposer()

        system_prompt = "You are a helpful assistant."
        tree_json = {"files": ["file1.py"]}
        dependencies_json = {"deps": ["pytest"]}
        file_summaries_json = {"summaries": []}
        spec_data = {"spec": "value"}

        result = composer.compose_structured_content(
            system_prompt,
            tree_json,
            dependencies_json,
            file_summaries_json,
            spec_data,
        )

        # Verify structure
        assert isinstance(result, dict)
        assert result["system_prompt"] == "You are a helpful assistant."
        assert result["repository_tree"] == {"files": ["file1.py"]}
        assert result["dependencies"] == {"deps": ["pytest"]}
        assert result["file_summaries"] == {"summaries": []}
        assert result["specification_data"] == {"spec": "value"}

    def test_compose_structured_content_strips_prompt(self) -> None:
        """Test that system prompt is stripped of whitespace."""
        composer = LlmInputComposer()

        result = composer.compose_structured_content(
            "  System prompt with spaces  ",
            {},
            {},
            {},
            {},
        )

        assert result["system_prompt"] == "System prompt with spaces"

    def test_compose_structured_content_validation_errors(self) -> None:
        """Test that structured content validates inputs."""
        composer = LlmInputComposer()

        # Empty system prompt
        with pytest.raises(ValueError, match="system_prompt cannot be empty"):
            composer.compose_structured_content("", {}, {}, {}, {})

        # None tree_json
        with pytest.raises(ValueError, match="tree_json cannot be None"):
            composer.compose_structured_content("prompt", None, {}, {}, {})

        # None dependencies_json
        with pytest.raises(ValueError, match="dependencies_json cannot be None"):
            composer.compose_structured_content("prompt", {}, None, {}, {})

        # None file_summaries_json
        with pytest.raises(ValueError, match="file_summaries_json cannot be None"):
            composer.compose_structured_content("prompt", {}, {}, None, {})

        # None spec_data
        with pytest.raises(ValueError, match="spec_data cannot be None"):
            composer.compose_structured_content("prompt", {}, {}, {}, None)

    def test_validate_repo_context_success(self) -> None:
        """Test successful validation of repo context."""
        composer = LlmInputComposer()

        # Should not raise any errors
        composer.validate_repo_context({}, [], {})
        composer.validate_repo_context({"tree": []}, {"deps": []}, {"summaries": []})

    def test_validate_repo_context_none_tree(self) -> None:
        """Test validation fails with None tree_json."""
        composer = LlmInputComposer()

        with pytest.raises(ValueError, match="tree_json cannot be None"):
            composer.validate_repo_context(None, {}, {})

    def test_validate_repo_context_none_dependencies(self) -> None:
        """Test validation fails with None dependencies_json."""
        composer = LlmInputComposer()

        with pytest.raises(ValueError, match="dependencies_json cannot be None"):
            composer.validate_repo_context({}, None, {})

    def test_validate_repo_context_none_summaries(self) -> None:
        """Test validation fails with None file_summaries_json."""
        composer = LlmInputComposer()

        with pytest.raises(ValueError, match="file_summaries_json cannot be None"):
            composer.validate_repo_context({}, {}, None)


class TestComposeLlmRequestPayload:
    """Tests for compose_llm_request_payload convenience function."""

    def test_string_format(self) -> None:
        """Test composition with string format."""
        result = compose_llm_request_payload(
            "System prompt",
            {"tree": []},
            {"deps": []},
            {"summaries": []},
            {"spec": "data"},
            format_type="string",
        )

        assert isinstance(result, str)
        assert "=== SYSTEM PROMPT ===" in result
        assert "System prompt" in result

    def test_structured_format(self) -> None:
        """Test composition with structured format."""
        result = compose_llm_request_payload(
            "System prompt",
            {"tree": []},
            {"deps": []},
            {"summaries": []},
            {"spec": "data"},
            format_type="structured",
        )

        assert isinstance(result, dict)
        assert result["system_prompt"] == "System prompt"
        assert result["repository_tree"] == {"tree": []}

    def test_default_format_is_string(self) -> None:
        """Test that default format_type is string."""
        result = compose_llm_request_payload(
            "System prompt",
            {},
            {},
            {},
            {},
        )

        assert isinstance(result, str)

    def test_unknown_format_type(self) -> None:
        """Test that unknown format_type raises error."""
        with pytest.raises(ValueError, match="Unknown format_type"):
            compose_llm_request_payload(
                "System prompt",
                {},
                {},
                {},
                {},
                format_type="invalid",
            )

    def test_validation_errors_propagate(self) -> None:
        """Test that validation errors are propagated."""
        with pytest.raises(ValueError, match="system_prompt cannot be empty"):
            compose_llm_request_payload("", {}, {}, {}, {})

        with pytest.raises(ValueError, match="tree_json cannot be None"):
            compose_llm_request_payload("prompt", None, {}, {}, {})


class TestLlmInputEdgeCases:
    """Tests for edge cases in LLM input composition."""

    def test_large_json_inputs(self) -> None:
        """Test composition with large JSON inputs."""
        composer = LlmInputComposer()

        # Create large inputs
        large_tree = {"files": [f"file{i}.py" for i in range(1000)]}
        large_deps = [{"name": f"dep{i}", "version": "1.0.0"} for i in range(500)]
        large_summaries = [{"path": f"file{i}.py", "summary": f"Summary {i}"} for i in range(100)]
        large_spec = {"items": [{"id": i, "data": f"data{i}"} for i in range(200)]}

        result = composer.compose_user_content(
            "Process this large dataset.",
            large_tree,
            large_deps,
            large_summaries,
            large_spec,
        )

        # Verify all sections are present
        assert "=== SYSTEM PROMPT ===" in result
        assert "=== REPOSITORY TREE ===" in result
        assert "file999.py" in result
        assert "dep499" in result

    def test_nested_json_structures(self) -> None:
        """Test composition with deeply nested JSON structures."""
        composer = LlmInputComposer()

        nested_data = {"level1": {"level2": {"level3": {"level4": {"value": "deep"}}}}}

        result = composer.compose_user_content(
            "prompt",
            nested_data,
            nested_data,
            nested_data,
            nested_data,
        )

        assert '"level4"' in result
        assert '"deep"' in result

    def test_special_characters_in_content(self) -> None:
        """Test composition with special characters."""
        composer = LlmInputComposer()

        special_chars = {
            "chars": "Special: @#$%^&*()[]{}|\\/<>?,.:;'\"",
            "unicode": "Emoji: 🚀 🎉 ✨",
            "newlines": "Line1\nLine2\nLine3",
        }

        result = composer.compose_user_content(
            "Handle special chars: @#$%",
            special_chars,
            special_chars,
            special_chars,
            special_chars,
        )

        assert "Special: @#$%^&*" in result
        # JSON encoding may escape unicode, so check for either form
        assert "🚀" in result or "\\ud83d\\ude80" in result

    def test_unexpected_keys_in_issues(self) -> None:
        """Test that composition handles spec data with unexpected keys."""
        composer = LlmInputComposer()

        spec_with_unexpected = {
            "standard_key": "value",
            "unexpected_key_123": "unexpected value",
            "nested": {"weird": {"structure": [1, 2, 3]}},
        }

        result = composer.compose_user_content(
            "prompt",
            {},
            {},
            {},
            spec_with_unexpected,
        )

        assert '"unexpected_key_123"' in result
        assert '"weird"' in result

    def test_empty_string_values_in_json(self) -> None:
        """Test composition with empty string values in JSON."""
        composer = LlmInputComposer()

        data_with_empty = {
            "empty": "",
            "whitespace": "   ",
            "normal": "value",
        }

        result = composer.compose_user_content(
            "prompt",
            data_with_empty,
            {},
            {},
            {},
        )

        assert '"empty": ""' in result
        assert '"whitespace": "   "' in result
