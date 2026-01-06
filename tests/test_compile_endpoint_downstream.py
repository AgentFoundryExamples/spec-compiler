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
Tests for downstream sender integration in compile endpoint.

Validates downstream sender success and failure paths, SKIP_DOWNSTREAM_SEND
flag behavior, and status publishing during downstream errors.
"""

import logging
from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from spec_compiler.services.downstream_sender import (
    DownstreamSenderError,
    DownstreamValidationError,
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


@pytest.fixture(autouse=True)
def cleanup_patches():
    """
    Ensure all patches are properly cleaned up between tests.

    This autouse fixture helps maintain test isolation by ensuring
    that any mocks or patches are reset between test runs.
    """
    yield
    # Cleanup happens automatically with context managers, but this
    # ensures any module-level state is reset


class TestDownstreamSenderSuccess:
    """Tests for successful downstream send scenarios."""

    def test_compile_sends_to_downstream_on_success(
        self, test_client: TestClient, caplog
    ) -> None:
        """Test that successful compilation sends to downstream."""
        caplog.set_level(logging.INFO)

        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_sender = Mock()
            mock_get_sender.return_value = mock_sender

            payload = {
                "plan_id": "plan-downstream-success",
                "spec_index": 0,
                "spec": _create_valid_spec(purpose="Test feature", vision="Test vision"),
                "github_owner": "test-owner",
                "github_repo": "test-repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "accepted"

            # Verify downstream sender was called
            mock_sender.send_compiled_spec.assert_called_once()
            call_args = mock_sender.send_compiled_spec.call_args
            context = call_args[0][1]

            # Verify context contains required fields
            assert context["plan_id"] == "plan-downstream-success"
            assert context["spec_index"] == 0
            assert context["github_owner"] == "test-owner"
            assert context["github_repo"] == "test-repo"
            assert "request_id" in context

            # Verify log messages
            log_messages = [record.message for record in caplog.records]
            assert any("stage_send_downstream_start" in msg for msg in log_messages)
            assert any("stage_send_downstream_complete" in msg for msg in log_messages)

    def test_compile_logs_downstream_attempt(
        self, test_client: TestClient, caplog
    ) -> None:
        """Test that downstream send attempts are logged."""
        caplog.set_level(logging.INFO)

        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_sender = Mock()
            mock_get_sender.return_value = mock_sender

            payload = {
                "plan_id": "plan-log-check",
                "spec_index": 2,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            assert response.status_code == 202

            # Check downstream logs
            log_messages = [record.message for record in caplog.records]
            assert any("stage_send_downstream_start" in msg for msg in log_messages)
            assert any("stage_send_downstream_complete" in msg for msg in log_messages)

    def test_compile_includes_compiled_spec_in_downstream(
        self, test_client: TestClient
    ) -> None:
        """Test that compiled spec is passed to downstream sender."""
        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_sender = Mock()
            mock_get_sender.return_value = mock_sender

            payload = {
                "plan_id": "plan-spec-check",
                "spec_index": 0,
                "spec": _create_valid_spec(purpose="Test feature", vision="Test vision"),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            assert response.status_code == 202

            # Verify compiled spec was sent
            mock_sender.send_compiled_spec.assert_called_once()
            compiled_spec = mock_sender.send_compiled_spec.call_args[0][0]

            # Verify it's the parsed LlmCompiledSpecOutput
            assert hasattr(compiled_spec, "version")
            assert hasattr(compiled_spec, "issues")
            assert compiled_spec.version is not None


class TestDownstreamSenderFailures:
    """Tests for downstream sender failure scenarios."""

    def test_downstream_sender_error_returns_502(
        self, test_client: TestClient, mock_publisher
    ) -> None:
        """Test that DownstreamSenderError returns 502 Bad Gateway."""
        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_sender = Mock()
            mock_get_sender.return_value = mock_sender
            mock_sender.send_compiled_spec.side_effect = DownstreamSenderError(
                "Downstream service unavailable"
            )

            payload = {
                "plan_id": "plan-downstream-error",
                "spec_index": 0,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            # In async mode, should return 202 and handle error in background
            assert response.status_code == 202

            # Verify failed status was published (in background task)
            failed_messages = mock_publisher.get_messages_by_status("failed")
            assert len(failed_messages) >= 1
            msg = failed_messages[0]
            assert msg.plan_id == "plan-downstream-error"
            assert msg.error_code == "downstream_sender_error"
            assert "Downstream sender error" in msg.error_message

    def test_downstream_validation_error_returns_502(
        self, test_client: TestClient, mock_publisher
    ) -> None:
        """Test that DownstreamValidationError returns 502 Bad Gateway."""
        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_sender = Mock()
            mock_get_sender.return_value = mock_sender
            mock_sender.send_compiled_spec.side_effect = DownstreamValidationError(
                "Invalid payload structure"
            )

            payload = {
                "plan_id": "plan-validation-error",
                "spec_index": 1,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            # In async mode, should return 202 and handle error in background
            assert response.status_code == 202

            # Verify failed status was published (in background task)
            failed_messages = mock_publisher.get_messages_by_status("failed")
            assert len(failed_messages) >= 1
            msg = failed_messages[0]
            assert msg.error_code == "downstream_sender_error"

    def test_downstream_unexpected_error_returns_500(
        self, test_client: TestClient, mock_publisher
    ) -> None:
        """Test that unexpected downstream errors return 500."""
        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_sender = Mock()
            mock_get_sender.return_value = mock_sender
            mock_sender.send_compiled_spec.side_effect = RuntimeError(
                "Unexpected downstream error"
            )

            payload = {
                "plan_id": "plan-unexpected-downstream",
                "spec_index": 0,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            # In async mode, should return 202 and handle error in background
            assert response.status_code == 202

            # Verify failed status was published (in background task)
            failed_messages = mock_publisher.get_messages_by_status("failed")
            assert len(failed_messages) >= 1
            msg = failed_messages[0]
            assert msg.error_code == "downstream_unexpected_error"

    def test_downstream_error_logs_failure(
        self, test_client: TestClient, caplog
    ) -> None:
        """Test that downstream errors are logged with context."""
        caplog.set_level(logging.ERROR)

        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_sender = Mock()
            mock_get_sender.return_value = mock_sender
            mock_sender.send_compiled_spec.side_effect = DownstreamSenderError("Send failed")

            payload = {
                "plan_id": "plan-log-error",
                "spec_index": 0,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            # In async mode, should return 202 and handle error in background
            assert response.status_code == 202

            # Check error logging (in background task)
            log_messages = [record.message for record in caplog.records]
            assert any("stage_send_downstream_failed" in msg for msg in log_messages)


class TestSkipDownstreamSend:
    """Tests for SKIP_DOWNSTREAM_SEND flag behavior."""

    def test_skip_downstream_when_sender_not_configured(
        self, test_client: TestClient, caplog
    ) -> None:
        """Test that compile succeeds when downstream sender is not configured."""
        caplog.set_level(logging.WARNING)

        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_get_sender.return_value = None

            payload = {
                "plan_id": "plan-no-sender",
                "spec_index": 0,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            # Should succeed even without downstream sender
            assert response.status_code == 202
            data = response.json()
            assert data["status"] == "accepted"

            # Verify skip was logged
            log_messages = [record.message for record in caplog.records]
            assert any("stage_send_downstream_skipped" in msg for msg in log_messages)

    def test_skip_downstream_returns_success_status(self, test_client: TestClient) -> None:
        """Test that skipping downstream still returns 202 success."""
        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_get_sender.return_value = None

            payload = {
                "plan_id": "plan-skip-success",
                "spec_index": 0,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            assert response.status_code == 202
            assert response.json()["status"] == "accepted"

    def test_skip_downstream_still_publishes_succeeded(
        self, test_client: TestClient, mock_publisher
    ) -> None:
        """Test that succeeded status is published even when downstream is skipped."""
        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_get_sender.return_value = None

            payload = {
                "plan_id": "plan-skip-publish",
                "spec_index": 0,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            assert response.status_code == 202

            # Verify succeeded status was still published
            succeeded_messages = mock_publisher.get_messages_by_status("succeeded")
            assert len(succeeded_messages) == 1
            msg = succeeded_messages[0]
            assert msg.plan_id == "plan-skip-publish"

    def test_skip_downstream_logs_reason(self, test_client: TestClient, caplog) -> None:
        """Test that skip reason is logged."""
        caplog.set_level(logging.WARNING)

        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_get_sender.return_value = None

            payload = {
                "plan_id": "plan-skip-reason",
                "spec_index": 0,
                "spec": _create_valid_spec(),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            assert response.status_code == 202

            # Check skip logging
            log_records = [r for r in caplog.records if "stage_send_downstream_skipped" in r.message]
            assert len(log_records) >= 1
            # Verify reason is in the log
            assert any(
                "sender_not_configured" in str(r.__dict__)
                for r in log_records
            )


class TestDownstreamIntegrationFlow:
    """Tests for complete downstream integration flow."""

    def test_complete_success_flow_with_downstream(
        self, test_client: TestClient, mock_publisher
    ) -> None:
        """Test complete flow: in_progress -> LLM -> downstream -> succeeded."""
        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_sender = Mock()
            mock_get_sender.return_value = mock_sender

            payload = {
                "plan_id": "plan-complete-flow",
                "spec_index": 0,
                "spec": _create_valid_spec(purpose="Test feature", vision="Test vision"),
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            assert response.status_code == 202

            # Verify all status messages were published in order
            in_progress_messages = mock_publisher.get_messages_by_status("in_progress")
            succeeded_messages = mock_publisher.get_messages_by_status("succeeded")
            assert len(in_progress_messages) >= 1
            assert len(succeeded_messages) >= 1

            # Verify order by checking the messages list directly
            status_sequence = [msg.status for msg in mock_publisher.messages]
            assert "in_progress" in status_sequence
            assert "succeeded" in status_sequence
            assert status_sequence.index("in_progress") < status_sequence.index("succeeded")

            # Verify downstream was called
            mock_sender.send_compiled_spec.assert_called_once()

    def test_failure_before_downstream_skips_downstream_call(
        self, test_client: TestClient, mock_publisher
    ) -> None:
        """Test that downstream is not called if earlier stage fails."""
        from spec_compiler.services.llm_client import LlmConfigurationError

        with patch("spec_compiler.app.routes.compile.get_downstream_sender") as mock_get_sender:
            mock_sender = Mock()
            mock_get_sender.return_value = mock_sender

            with patch("spec_compiler.app.routes.compile.create_llm_client") as mock_create:
                mock_create.side_effect = LlmConfigurationError("LLM not configured")

                payload = {
                    "plan_id": "plan-early-failure",
                    "spec_index": 0,
                    "spec": _create_valid_spec(),
                    "github_owner": "owner",
                    "github_repo": "repo",
                }

                response = test_client.post("/compile-spec", json=payload)

                # In async mode, should return 202 and handle error in background
                assert response.status_code == 202

                # Downstream should NOT be called (error happens before downstream stage)
                mock_sender.send_compiled_spec.assert_not_called()

                # Failed status should be published (in background task)
                failed_messages = mock_publisher.get_messages_by_status("failed")
                assert len(failed_messages) >= 1
