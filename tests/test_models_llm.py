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
Tests for LLM envelope models.

Validates LLM-related models used for typing and future integration.
"""

import pytest
from pydantic import ValidationError

from spec_compiler.models.llm import (
    GitHubAuthToken,
    LlmRequestEnvelope,
    LlmResponseEnvelope,
    RepoContextPayload,
    SystemPromptConfig,
)


class TestSystemPromptConfig:
    """Tests for SystemPromptConfig model."""

    def test_default_values(self) -> None:
        """Test that model can be instantiated with default values."""
        config = SystemPromptConfig()
        assert config.template == ""
        assert config.variables == {}
        assert config.max_tokens == 4096

    def test_custom_values(self) -> None:
        """Test model with custom values."""
        config = SystemPromptConfig(
            template="You are a helpful assistant. Context: {context}",
            variables={"context": "coding", "language": "Python"},
            max_tokens=2048,
        )
        assert config.template == "You are a helpful assistant. Context: {context}"
        assert config.variables == {"context": "coding", "language": "Python"}
        assert config.max_tokens == 2048

    def test_max_tokens_must_be_positive(self) -> None:
        """Test that max_tokens must be greater than 0."""
        with pytest.raises(ValidationError) as exc_info:
            SystemPromptConfig(max_tokens=0)
        errors = exc_info.value.errors()
        assert any(
            error["loc"] == ("max_tokens",) and error["type"] == "greater_than" for error in errors
        )

    def test_max_tokens_negative_raises_error(self) -> None:
        """Test that negative max_tokens raises validation error."""
        with pytest.raises(ValidationError):
            SystemPromptConfig(max_tokens=-100)


class TestRepoContextPayload:
    """Tests for RepoContextPayload model."""

    def test_default_empty_lists(self) -> None:
        """Test that lists default to empty."""
        context = RepoContextPayload()
        assert context.tree == []
        assert context.dependencies == []
        assert context.file_summaries == []

    def test_with_tree_data(self) -> None:
        """Test with tree data."""
        tree_data = [
            {"path": "src/main.py", "type": "file"},
            {"path": "tests/", "type": "directory"},
        ]
        context = RepoContextPayload(tree=tree_data)
        assert context.tree == tree_data
        assert context.dependencies == []
        assert context.file_summaries == []

    def test_with_dependencies_data(self) -> None:
        """Test with dependencies data."""
        deps_data = [
            {"name": "fastapi", "version": "0.115.5"},
            {"name": "pydantic", "version": "2.10.3"},
        ]
        context = RepoContextPayload(dependencies=deps_data)
        assert context.dependencies == deps_data

    def test_with_file_summaries_data(self) -> None:
        """Test with file summaries data."""
        summaries = [
            {"path": "src/main.py", "summary": "Main application entry point"},
            {"path": "src/config.py", "summary": "Configuration management"},
        ]
        context = RepoContextPayload(file_summaries=summaries)
        assert context.file_summaries == summaries

    def test_with_all_fields(self) -> None:
        """Test with all fields populated."""
        context = RepoContextPayload(
            tree=[{"path": "src/", "type": "dir"}],
            dependencies=[{"name": "pytest", "version": "8.3.4"}],
            file_summaries=[{"path": "README.md", "summary": "Documentation"}],
        )
        assert len(context.tree) == 1
        assert len(context.dependencies) == 1
        assert len(context.file_summaries) == 1


class TestLlmRequestEnvelope:
    """Tests for LlmRequestEnvelope model."""

    def test_minimal_request(self) -> None:
        """Test request with only required fields."""
        request = LlmRequestEnvelope(request_id="req-123")
        assert request.request_id == "req-123"
        assert request.model == "gpt-5.1"
        assert isinstance(request.system_prompt, SystemPromptConfig)
        assert request.user_prompt == ""
        assert request.repo_context is None
        assert request.metadata == {}

    def test_full_request(self) -> None:
        """Test request with all fields."""
        system_prompt = SystemPromptConfig(
            template="System prompt",
            variables={"var": "value"},
            max_tokens=1024,
        )
        repo_context = RepoContextPayload(
            tree=[{"path": "src/"}],
            dependencies=[{"name": "lib"}],
            file_summaries=[{"path": "file.py"}],
        )
        request = LlmRequestEnvelope(
            request_id="req-full",
            model="claude-sonnet-4.5",
            system_prompt=system_prompt,
            user_prompt="User question",
            repo_context=repo_context,
            metadata={"key": "value"},
        )
        assert request.request_id == "req-full"
        assert request.model == "claude-sonnet-4.5"
        assert request.system_prompt.template == "System prompt"
        assert request.user_prompt == "User question"
        assert request.repo_context is not None
        assert request.repo_context.tree == [{"path": "src/"}]
        assert request.metadata == {"key": "value"}

    def test_default_model_is_gpt_5_1(self) -> None:
        """Test that default model is gpt-5.1."""
        request = LlmRequestEnvelope(request_id="req-default")
        assert request.model == "gpt-5.1"

    def test_custom_model(self) -> None:
        """Test with custom model."""
        request = LlmRequestEnvelope(
            request_id="req-gemini",
            model="gemini-3.0-pro",
        )
        assert request.model == "gemini-3.0-pro"


class TestLlmResponseEnvelope:
    """Tests for LlmResponseEnvelope model."""

    def test_minimal_response(self) -> None:
        """Test response with only required fields."""
        response = LlmResponseEnvelope(request_id="req-123")
        assert response.request_id == "req-123"
        assert response.status == "pending"
        assert response.content == ""
        assert response.model is None
        assert response.usage is None
        assert response.metadata == {}

    def test_full_response(self) -> None:
        """Test response with all fields."""
        response = LlmResponseEnvelope(
            request_id="req-full",
            status="success",
            content="LLM generated content",
            model="gpt-5.1",
            usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
            metadata={"duration_ms": 1234, "cached": False},
        )
        assert response.request_id == "req-full"
        assert response.status == "success"
        assert response.content == "LLM generated content"
        assert response.model == "gpt-5.1"
        assert response.usage == {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
        }
        assert response.metadata == {"duration_ms": 1234, "cached": False}

    def test_default_status_is_pending(self) -> None:
        """Test that default status is pending."""
        response = LlmResponseEnvelope(request_id="req-default")
        assert response.status == "pending"

    def test_various_status_values(self) -> None:
        """Test different status values."""
        for status in ["success", "error", "pending", "timeout", "rate_limited"]:
            response = LlmResponseEnvelope(request_id="req-status", status=status)
            assert response.status == status

    def test_empty_usage(self) -> None:
        """Test with empty usage dictionary."""
        response = LlmResponseEnvelope(
            request_id="req-empty-usage",
            usage={},
        )
        assert response.usage == {}

    def test_model_serialization(self) -> None:
        """Test that model can be serialized."""
        response = LlmResponseEnvelope(
            request_id="req-serialize",
            status="success",
            content="test content",
            model="test-model",
            usage={"tokens": 100},
            metadata={"test": "data"},
        )
        data = response.model_dump()
        assert data["request_id"] == "req-serialize"
        assert data["status"] == "success"
        assert data["content"] == "test content"
        assert data["model"] == "test-model"
        assert data["usage"] == {"tokens": 100}
        assert data["metadata"] == {"test": "data"}

    def test_status_literal_enforcement(self) -> None:
        """Test that status field only accepts allowed literal values."""
        from pydantic import ValidationError

        # Valid statuses should work
        for valid_status in ["success", "error", "pending", "timeout", "rate_limited"]:
            response = LlmResponseEnvelope(
                request_id="req-test",
                status=valid_status,
            )
            assert response.status == valid_status

        # Invalid status should raise validation error
        with pytest.raises(ValidationError) as exc_info:
            LlmResponseEnvelope(
                request_id="req-invalid",
                status="invalid_status",
            )
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("status",) for error in errors)


class TestLlmModelsIntegration:
    """Integration tests for LLM models working together."""

    def test_request_with_nested_models(self) -> None:
        """Test request envelope with nested model structures."""
        system_prompt = SystemPromptConfig(
            template="You are an expert in {domain}",
            variables={"domain": "Python programming"},
            max_tokens=8192,
        )
        repo_context = RepoContextPayload(
            tree=[
                {"path": "src/main.py", "type": "file", "size": 1024},
                {"path": "tests/", "type": "directory", "children": 5},
            ],
            dependencies=[
                {"name": "fastapi", "version": "0.115.5", "type": "runtime"},
                {"name": "pytest", "version": "8.3.4", "type": "dev"},
            ],
            file_summaries=[
                {"path": "src/main.py", "summary": "Entry point", "lines": 100},
                {"path": "src/config.py", "summary": "Settings", "lines": 50},
            ],
        )
        request = LlmRequestEnvelope(
            request_id="req-integration",
            model="gpt-5.1",
            system_prompt=system_prompt,
            user_prompt="How do I implement authentication?",
            repo_context=repo_context,
            metadata={
                "user_id": "user-123",
                "timestamp": "2026-01-01T12:00:00Z",
                "priority": "high",
            },
        )

        # Verify all data is correctly stored
        assert request.request_id == "req-integration"
        assert request.system_prompt.variables["domain"] == "Python programming"
        assert request.system_prompt.max_tokens == 8192
        assert len(request.repo_context.tree) == 2
        assert len(request.repo_context.dependencies) == 2
        assert len(request.repo_context.file_summaries) == 2
        assert request.metadata["priority"] == "high"

    def test_models_can_be_serialized_and_deserialized(self) -> None:
        """Test that models maintain data integrity through serialization."""
        original = LlmResponseEnvelope(
            request_id="req-roundtrip",
            status="success",
            content="Response content",
            model="gpt-5.1",
            usage={"total_tokens": 200},
            metadata={"cached": True},
        )

        # Serialize to dict
        data = original.model_dump()

        # Deserialize back to model
        restored = LlmResponseEnvelope(**data)

        # Verify data integrity
        assert restored.request_id == original.request_id
        assert restored.status == original.status
        assert restored.content == original.content
        assert restored.model == original.model
        assert restored.usage == original.usage
        assert restored.metadata == original.metadata


class TestGitHubAuthToken:
    """Tests for GitHubAuthToken model."""

    def test_minimal_token(self) -> None:
        """Test token with only required fields."""
        token = GitHubAuthToken(access_token="gho_test123456789")
        assert token.access_token == "gho_test123456789"
        assert token.token_type == "bearer"
        assert token.expires_at is None
        assert token.scope is None
        assert token.created_at is not None

    def test_full_token(self) -> None:
        """Test token with all fields."""
        from datetime import datetime

        created = datetime(2026, 1, 1, 12, 0, 0)
        token = GitHubAuthToken(
            access_token="gho_fulltoken123",
            token_type="bearer",
            expires_at="2026-12-31T23:59:59+00:00",
            scope="repo,user:email,read:org",
            created_at=created,
        )
        assert token.access_token == "gho_fulltoken123"
        assert token.token_type == "bearer"
        assert token.expires_at == "2026-12-31T23:59:59+00:00"
        assert token.scope == "repo,user:email,read:org"
        assert token.created_at == created

    def test_non_expiring_token(self) -> None:
        """Test token without expiration (common for user tokens)."""
        token = GitHubAuthToken(
            access_token="gho_noexpiry",
            expires_at=None,
        )
        assert token.access_token == "gho_noexpiry"
        assert token.expires_at is None

    def test_empty_access_token_raises_error(self) -> None:
        """Test that empty access token raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            GitHubAuthToken(access_token="")
        errors = exc_info.value.errors()
        assert any(error["loc"] == ("access_token",) for error in errors)

    def test_default_token_type(self) -> None:
        """Test that token_type defaults to 'bearer'."""
        token = GitHubAuthToken(access_token="gho_default")
        assert token.token_type == "bearer"

    def test_custom_token_type(self) -> None:
        """Test with custom token type."""
        token = GitHubAuthToken(
            access_token="ghp_custom",
            token_type="personal",
        )
        assert token.token_type == "personal"

    def test_token_with_scopes(self) -> None:
        """Test token with OAuth scopes."""
        token = GitHubAuthToken(
            access_token="gho_scoped",
            scope="repo,write:org,admin:repo_hook",
        )
        assert token.scope == "repo,write:org,admin:repo_hook"

    def test_token_serialization(self) -> None:
        """Test that token can be serialized."""
        from datetime import datetime

        created = datetime(2026, 1, 1, 12, 0, 0)
        token = GitHubAuthToken(
            access_token="gho_serialize",
            token_type="bearer",
            expires_at="2026-12-31T23:59:59+00:00",
            scope="repo,user",
            created_at=created,
        )
        data = token.model_dump()
        assert data["access_token"] == "gho_serialize"
        assert data["token_type"] == "bearer"
        assert data["expires_at"] == "2026-12-31T23:59:59+00:00"
        assert data["scope"] == "repo,user"
        assert isinstance(data["created_at"], datetime)

    def test_token_deserialization(self) -> None:
        """Test that token can be deserialized from dict."""
        from datetime import datetime

        data = {
            "access_token": "gho_deserialize",
            "token_type": "bearer",
            "expires_at": "2026-12-31T23:59:59+00:00",
            "scope": "repo",
            "created_at": datetime(2026, 1, 1, 12, 0, 0),
        }
        token = GitHubAuthToken(**data)
        assert token.access_token == "gho_deserialize"
        assert token.expires_at == "2026-12-31T23:59:59+00:00"
        assert token.scope == "repo"

    def test_token_roundtrip_serialization(self) -> None:
        """Test that token maintains data integrity through serialization."""
        from datetime import datetime

        original = GitHubAuthToken(
            access_token="gho_roundtrip",
            token_type="bearer",
            expires_at="2026-06-15T12:00:00+00:00",
            scope="repo,user:email",
            created_at=datetime(2026, 1, 1),
        )

        # Serialize and deserialize
        data = original.model_dump()
        restored = GitHubAuthToken(**data)

        # Verify data integrity
        assert restored.access_token == original.access_token
        assert restored.token_type == original.token_type
        assert restored.expires_at == original.expires_at
        assert restored.scope == original.scope
        assert restored.created_at == original.created_at
