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
    LlmInputStructure,
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

    def test_default_format_is_separated(self) -> None:
        """Test that default format_type is separated (NEW behavior)."""
        result = compose_llm_request_payload(
            "System prompt",
            {},
            {},
            {},
            {},
        )

        # New default is separated
        assert isinstance(result, LlmInputStructure)
        assert result.system_prompt == "System prompt"
        assert "=====TREE=====" in result.user_content
        assert "```json" in result.user_content

    def test_separated_format(self) -> None:
        """Test composition with separated format (NEW recommended)."""
        result = compose_llm_request_payload(
            "System prompt",
            {"tree": []},
            {"deps": []},
            {"summaries": []},
            {"spec": "data"},
            format_type="separated",
        )

        assert isinstance(result, LlmInputStructure)
        assert result.system_prompt == "System prompt"
        assert "=====TREE=====" in result.user_content
        assert '"tree": []' in result.user_content
        assert "```json" in result.user_content
        # System prompt should NOT be in user content
        assert "System prompt" not in result.user_content

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


class TestNewSeparatedComposition:
    """Tests for the new separated composition approach with JSON fencing."""

    def test_compose_separated_returns_structure(self) -> None:
        """Test that compose_separated returns LlmInputStructure."""
        composer = LlmInputComposer()

        result = composer.compose_separated(
            "System prompt text",
            {"tree": ["file1.py"]},
            {"deps": ["pytest"]},
            {"summaries": ["summary1"]},
            {"spec": "data"},
        )

        assert isinstance(result, LlmInputStructure)
        assert result.system_prompt == "System prompt text"
        assert isinstance(result.user_content, str)

    def test_compose_separated_system_prompt_not_in_user_content(self) -> None:
        """Test that system prompt is NOT included in user content."""
        composer = LlmInputComposer()

        result = composer.compose_separated(
            "This is the system prompt",
            {},
            {},
            {},
            {},
        )

        # System prompt should be in separate field
        assert result.system_prompt == "This is the system prompt"
        # But NOT in user content
        assert "This is the system prompt" not in result.user_content
        assert "SYSTEM PROMPT" not in result.user_content

    def test_compose_separated_has_json_fences(self) -> None:
        """Test that user content has labeled JSON fenced blocks."""
        composer = LlmInputComposer()

        result = composer.compose_separated(
            "System prompt",
            {"tree": ["file1.py"]},
            {"deps": ["pytest"]},
            {"summaries": []},
            {"spec": "data"},
        )

        # Check for labeled fences
        assert "=====TREE=====" in result.user_content
        assert "=====DEPENDENCIES=====" in result.user_content
        assert "=====FILE_SUMMARIES=====" in result.user_content
        assert "=====SPECIFICATION=====" in result.user_content

        # Check for JSON fences
        assert "```json" in result.user_content
        assert "```" in result.user_content

        # Check content structure more robustly
        # The content should have these patterns regardless of formatting
        user_content = result.user_content
        assert "file1.py" in user_content  # Tree data is present
        assert "pytest" in user_content  # Dependencies data is present

    def test_compose_user_content_only_no_system_prompt(self) -> None:
        """Test _compose_user_content_only internal method."""
        composer = LlmInputComposer()

        result = composer._compose_user_content_only(
            {"tree": []},
            {"deps": []},
            {"summaries": []},
            {"spec": "data"},
        )

        # Should have fenced blocks
        assert "=====TREE=====" in result
        assert "```json" in result

    def test_compose_user_content_only_validates_none(self) -> None:
        """Test that _compose_user_content_only validates None inputs."""
        composer = LlmInputComposer()

        with pytest.raises(ValueError, match="tree_json cannot be None"):
            composer._compose_user_content_only(None, {}, {}, {})

        with pytest.raises(ValueError, match="dependencies_json cannot be None"):
            composer._compose_user_content_only({}, None, {}, {})

        with pytest.raises(ValueError, match="file_summaries_json cannot be None"):
            composer._compose_user_content_only({}, {}, None, {})

        with pytest.raises(ValueError, match="spec_data cannot be None"):
            composer._compose_user_content_only({}, {}, {}, None)

    def test_json_fencing_with_complete_artifacts(self) -> None:
        """Test that complete JSON artifacts are embedded verbatim."""
        composer = LlmInputComposer()

        tree_data = [
            {"path": "src/main.py", "type": "file", "size": 1234},
            {"path": "tests/", "type": "dir"},
        ]
        deps_data = [
            {"name": "fastapi", "version": "0.115.5", "ecosystem": "pip"},
            {"name": "pydantic", "version": "2.10.3", "ecosystem": "pip"},
        ]

        result = composer.compose_separated(
            "Analyze this code",
            tree_data,
            deps_data,
            [],
            {"task": "refactor"},
        )

        # Verify complete JSON is embedded
        assert '"path": "src/main.py"' in result.user_content
        assert '"size": 1234' in result.user_content
        assert '"name": "fastapi"' in result.user_content
        assert '"version": "0.115.5"' in result.user_content
        assert '"ecosystem": "pip"' in result.user_content

    def test_empty_and_malformed_json_handling(self) -> None:
        """Test handling of empty JSON artifacts."""
        composer = LlmInputComposer()

        # Empty artifacts should still produce fenced blocks
        result = composer.compose_separated(
            "Test prompt",
            [],  # Empty tree
            {},  # Empty dependencies
            [],  # Empty summaries
            {},  # Empty spec
        )

        # Fences should still be present
        assert "=====TREE=====" in result.user_content
        assert "=====DEPENDENCIES=====" in result.user_content
        assert "```json" in result.user_content
        assert "[]" in result.user_content or "{}" in result.user_content

    def test_deterministic_ordering(self) -> None:
        """Test that artifact ordering is deterministic."""
        composer = LlmInputComposer()

        result1 = composer.compose_separated(
            "System",
            {"a": 1, "b": 2},
            {"c": 3},
            {"d": 4},
            {"e": 5},
        )

        result2 = composer.compose_separated(
            "System",
            {"a": 1, "b": 2},
            {"c": 3},
            {"d": 4},
            {"e": 5},
        )

        # Results should be identical for same inputs
        assert result1.user_content == result2.user_content
        assert result1.system_prompt == result2.system_prompt

        # Order should be: TREE, DEPENDENCIES, FILE_SUMMARIES, SPECIFICATION
        content = result1.user_content
        tree_pos = content.find("=====TREE=====")
        deps_pos = content.find("=====DEPENDENCIES=====")
        summaries_pos = content.find("=====FILE_SUMMARIES=====")
        spec_pos = content.find("=====SPECIFICATION=====")

        assert tree_pos < deps_pos < summaries_pos < spec_pos


class TestJsonFencedBlockParsing:
    """Tests to validate that JSON inside fenced blocks is parseable."""

    def test_json_in_fences_is_valid_and_parseable(self) -> None:
        """Test that JSON inside fenced blocks can be extracted and parsed."""
        import json
        import re

        composer = LlmInputComposer()

        tree_data = [{"path": "src/main.py", "type": "file", "size": 1234}]
        deps_data = [{"name": "fastapi", "version": "0.115.5"}]
        summaries_data = [{"path": "README.md", "summary": "Documentation"}]
        spec_data = {"task": "refactor", "priority": "high"}

        result = composer.compose_separated(
            "Analyze code",
            tree_data,
            deps_data,
            summaries_data,
            spec_data,
        )

        # Extract JSON blocks using regex
        json_pattern = r"```json\n(.*?)\n```"
        json_blocks = re.findall(json_pattern, result.user_content, re.DOTALL)

        # Should have 4 JSON blocks
        assert len(json_blocks) == 4

        # Parse each block to ensure it's valid JSON
        parsed_blocks = []
        for block in json_blocks:
            try:
                parsed_data = json.loads(block)
                parsed_blocks.append(parsed_data)
            except json.JSONDecodeError as e:
                pytest.fail(f"Failed to parse JSON block: {e}\nBlock content: {block}")

        # Verify parsed data matches original
        assert parsed_blocks[0] == tree_data
        assert parsed_blocks[1] == deps_data
        assert parsed_blocks[2] == summaries_data
        assert parsed_blocks[3] == spec_data

    def test_empty_json_structures_are_valid(self) -> None:
        """Test that empty JSON structures in fences are valid."""
        import json
        import re

        composer = LlmInputComposer()

        result = composer.compose_separated(
            "Process empty data",
            [],  # Empty list
            {},  # Empty dict
            [],  # Empty list
            {},  # Empty dict
        )

        # Extract JSON blocks
        json_pattern = r"```json\n(.*?)\n```"
        json_blocks = re.findall(json_pattern, result.user_content, re.DOTALL)

        assert len(json_blocks) == 4

        # All should be valid JSON
        for block in json_blocks:
            parsed = json.loads(block)
            assert parsed in [[], {}]

    def test_complex_nested_json_is_parseable(self) -> None:
        """Test that complex nested JSON structures remain valid in fences."""
        import json
        import re

        composer = LlmInputComposer()

        complex_data = {
            "level1": {
                "level2": {
                    "level3": {"array": [1, 2, 3], "string": "value", "null": None, "bool": True}
                }
            }
        }

        result = composer.compose_separated(
            "Process nested data",
            complex_data,
            complex_data,
            complex_data,
            complex_data,
        )

        # Extract JSON blocks
        json_pattern = r"```json\n(.*?)\n```"
        json_blocks = re.findall(json_pattern, result.user_content, re.DOTALL)

        # Parse and verify all blocks
        for block in json_blocks:
            parsed = json.loads(block)
            assert parsed == complex_data

    def test_special_characters_in_json_are_preserved(self) -> None:
        """Test that special characters in JSON are properly escaped and parseable."""
        import json
        import re


def _create_valid_spec(
    purpose: str = "Test purpose",
    vision: str = "Test vision",
    must: list[str] | None = None,
    dont: list[str] | None = None,
    nice: list[str] | None = None,
    assumptions: list[str] | None = None,
) -> dict:
    """Helper to create a valid spec dictionary for testing."""
    return {
        "purpose": purpose,
        "vision": vision,
        "must": must if must is not None else [],
        "dont": dont if dont is not None else [],
        "nice": nice if nice is not None else [],
        "assumptions": assumptions if assumptions is not None else [],
    }



        composer = LlmInputComposer()

        special_data = {
            "quotes": 'String with "quotes"',
            "backslash": "Path\\with\\backslashes",
            "newline": "Line1\nLine2",
            "unicode": "Unicode: 🚀 ✨",
        }

        result = composer.compose_separated("Handle special chars", special_data, {}, {}, {})

        # Extract first JSON block (tree)
        json_pattern = r"```json\n(.*?)\n```"
        json_blocks = re.findall(json_pattern, result.user_content, re.DOTALL)

        # Parse and verify special characters are preserved
        parsed = json.loads(json_blocks[0])
        assert parsed == special_data
        assert parsed["quotes"] == 'String with "quotes"'
        assert parsed["backslash"] == "Path\\with\\backslashes"
        assert parsed["newline"] == "Line1\nLine2"
        assert parsed["unicode"] == "Unicode: 🚀 ✨"
