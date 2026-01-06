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
Tests for models package helpers.

Tests for the helper functions exposed by the models package.
"""

import uuid

from spec_compiler.models import create_llm_response_stub, generate_request_id
from spec_compiler.models.llm import LlmResponseEnvelope


class TestGenerateRequestId:
    """Tests for generate_request_id helper function."""

    def test_generates_valid_uuid(self) -> None:
        """Test that function generates a valid UUID string."""
        request_id = generate_request_id()
        # Should be able to parse as UUID
        parsed_uuid = uuid.UUID(request_id)
        assert str(parsed_uuid) == request_id

    def test_generates_unique_ids(self) -> None:
        """Test that function generates unique IDs on each call."""
        ids = [generate_request_id() for _ in range(100)]
        # All IDs should be unique
        assert len(ids) == len(set(ids))

    def test_returns_string(self) -> None:
        """Test that function returns a string."""
        request_id = generate_request_id()
        assert isinstance(request_id, str)

    def test_uuid_format(self) -> None:
        """Test that generated ID follows UUID format."""
        request_id = generate_request_id()
        # UUID4 format: xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx
        parts = request_id.split("-")
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12


class TestCreateLlmResponseStub:
    """Tests for create_llm_response_stub helper function."""

    def test_creates_stub_with_defaults(self) -> None:
        """Test creating stub with default values."""
        stub = create_llm_response_stub("req-123")
        assert isinstance(stub, LlmResponseEnvelope)
        assert stub.request_id == "req-123"
        assert stub.status == "pending"
        assert stub.content == ""
        assert stub.metadata == {}

    def test_creates_stub_with_custom_status(self) -> None:
        """Test creating stub with custom status."""
        stub = create_llm_response_stub("req-456", status="success")
        assert stub.request_id == "req-456"
        assert stub.status == "success"
        assert stub.content == ""

    def test_creates_stub_with_custom_content(self) -> None:
        """Test creating stub with custom content."""
        stub = create_llm_response_stub("req-789", content="Test content")
        assert stub.request_id == "req-789"
        assert stub.status == "pending"
        assert stub.content == "Test content"

    def test_creates_stub_with_all_parameters(self) -> None:
        """Test creating stub with all parameters."""
        stub = create_llm_response_stub(
            "req-full",
            status="error",
            content="Error message",
        )
        assert stub.request_id == "req-full"
        assert stub.status == "error"
        assert stub.content == "Error message"
        assert stub.metadata == {}

    def test_stub_is_valid_llm_response_envelope(self) -> None:
        """Test that stub can be used as LlmResponseEnvelope."""
        stub = create_llm_response_stub("req-valid")
        # Should be serializable
        data = stub.model_dump()
        assert "request_id" in data
        assert "status" in data
        assert "content" in data
        assert "metadata" in data

    def test_stub_with_custom_metadata(self) -> None:
        """Test creating stub with custom metadata."""
        metadata = {"key": "value", "count": 42}
        stub = create_llm_response_stub(
            "req-meta",
            status="success",
            content="test",
            metadata=metadata,
        )
        assert stub.metadata == {"key": "value", "count": 42}

    def test_multiple_stubs_are_independent(self) -> None:
        """Test that creating multiple stubs creates independent objects."""
        stub1 = create_llm_response_stub("req-1", status="pending")
        stub2 = create_llm_response_stub("req-2", status="success")

        assert stub1.request_id != stub2.request_id
        assert stub1.status != stub2.status

        # Modifying metadata on one should not affect the other
        stub1.metadata["test"] = "value1"
        stub2.metadata["test"] = "value2"
        assert stub1.metadata != stub2.metadata


class TestModelsPackageExports:
    """Tests for models package exports."""

    def test_package_exports_all_models(self) -> None:
        """Test that all expected models are exported from package."""
        from spec_compiler import models

        # Check that all expected exports exist
        assert hasattr(models, "CompileRequest")
        assert hasattr(models, "CompileResponse")
        assert hasattr(models, "SystemPromptConfig")
        assert hasattr(models, "RepoContextPayload")
        assert hasattr(models, "LlmRequestEnvelope")
        assert hasattr(models, "LlmResponseEnvelope")
        assert hasattr(models, "generate_request_id")
        assert hasattr(models, "create_llm_response_stub")

    def test_models_can_be_imported_from_main_package(self) -> None:
        """Test that models can be imported from main spec_compiler package."""
        from spec_compiler import (
            CompileRequest,
            CompileResponse,
            LlmRequestEnvelope,
            LlmResponseEnvelope,
            RepoContextPayload,
            SystemPromptConfig,
            create_llm_response_stub,
            generate_request_id,
        )

        # Verify imports are the correct types
        assert CompileRequest.__name__ == "CompileRequest"
        assert CompileResponse.__name__ == "CompileResponse"
        assert SystemPromptConfig.__name__ == "SystemPromptConfig"
        assert RepoContextPayload.__name__ == "RepoContextPayload"
        assert LlmRequestEnvelope.__name__ == "LlmRequestEnvelope"
        assert LlmResponseEnvelope.__name__ == "LlmResponseEnvelope"
        assert callable(generate_request_id)
        assert callable(create_llm_response_stub)

    def test_models_can_be_used_together(self) -> None:
        """Test that exported models and helpers work together."""
        from spec_compiler import (
            CompileRequest,
            CompileResponse,
            create_llm_response_stub,
            generate_request_id,
        )


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



        # Generate request ID
        request_id = generate_request_id()

        # Create compile request
        compile_req = CompileRequest(
            plan_id="test-plan",
            spec_index=0,
            spec=_create_valid_spec(),
            github_owner="owner",
            github_repo="repo",
        )

        # Create compile response
        compile_resp = CompileResponse(
            request_id=request_id,
            plan_id=compile_req.plan_id,
            spec_index=compile_req.spec_index,
            status="accepted",
        )

        # Create LLM response stub
        llm_stub = create_llm_response_stub(request_id)

        # Verify everything works together
        assert compile_resp.request_id == llm_stub.request_id
        assert compile_resp.plan_id == compile_req.plan_id
        assert uuid.UUID(request_id)  # Verify it's a valid UUID
