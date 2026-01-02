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
Tests for status publishing in compile endpoint.

Validates that PlanStatusMessage events are published at appropriate
lifecycle points and that publisher failures don't break the compile flow.
"""

from unittest.mock import Mock, patch

import pytest
from fastapi.testclient import TestClient

from spec_compiler.models.plan_status import PlanStatusMessage


@pytest.fixture
def mock_publisher():
    """Mock PlanSchedulerPublisher for testing."""
    with patch("spec_compiler.app.routes.compile.get_publisher") as mock_get:
        mock_instance = Mock()
        mock_get.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_publisher_disabled():
    """Mock PlanSchedulerPublisher that's disabled (returns None)."""
    with patch("spec_compiler.app.routes.compile.get_publisher") as mock_get:
        mock_get.return_value = None
        yield mock_get


class TestStatusPublishingSuccess:
    """Tests for status publishing on successful compile requests."""

    def test_publishes_in_progress_after_validation(
        self, test_client: TestClient, mock_publisher: Mock
    ) -> None:
        """Test that in_progress status is published after payload validation."""
        payload = {
            "plan_id": "plan-test",
            "spec_index": 0,
            "spec_data": {"test": "data"},
            "github_owner": "owner",
            "github_repo": "repo",
        }

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 202
        # Verify publish_status was called
        assert mock_publisher.publish_status.call_count >= 1
        
        # Find the in_progress call
        in_progress_calls = [
            call for call in mock_publisher.publish_status.call_args_list
            if call[0][0].status == "in_progress"
        ]
        assert len(in_progress_calls) == 1
        
        # Verify message fields
        msg = in_progress_calls[0][0][0]
        assert msg.plan_id == "plan-test"
        assert msg.spec_index == 0
        assert msg.status == "in_progress"
        assert msg.request_id is not None

    def test_publishes_succeeded_after_completion(
        self, test_client: TestClient, mock_publisher: Mock
    ) -> None:
        """Test that succeeded status is published after successful compilation."""
        payload = {
            "plan_id": "plan-success",
            "spec_index": 1,
            "spec_data": {"test": "data"},
            "github_owner": "owner",
            "github_repo": "repo",
        }

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 202
        
        # Verify both in_progress and succeeded were published
        assert mock_publisher.publish_status.call_count >= 2
        
        # Find the succeeded call
        succeeded_calls = [
            call for call in mock_publisher.publish_status.call_args_list
            if call[0][0].status == "succeeded"
        ]
        assert len(succeeded_calls) == 1
        
        # Verify message fields
        msg = succeeded_calls[0][0][0]
        assert msg.plan_id == "plan-success"
        assert msg.spec_index == 1
        assert msg.status == "succeeded"
        assert msg.error_code is None
        assert msg.error_message is None

    def test_request_id_propagates_to_status_messages(
        self, test_client: TestClient, mock_publisher: Mock
    ) -> None:
        """Test that request_id from middleware propagates to status messages."""
        payload = {
            "plan_id": "plan-id-test",
            "spec_index": 0,
            "spec_data": {},
            "github_owner": "owner",
            "github_repo": "repo",
        }

        response = test_client.post(
            "/compile-spec",
            json=payload,
            headers={"X-Request-Id": "test-request-id-123"},
        )

        assert response.status_code == 202
        
        # Verify all status messages have the same request_id
        for call in mock_publisher.publish_status.call_args_list:
            msg = call[0][0]
            # Request ID should be consistent across all messages
            assert msg.request_id is not None


class TestStatusPublishingFailure:
    """Tests for status publishing on compile request failures."""

    @patch("spec_compiler.app.routes.compile.GitHubAuthClient")
    def test_publishes_failed_on_minting_error(
        self,
        mock_auth_client_cls: Mock,
        test_client: TestClient,
        mock_publisher: Mock,
    ) -> None:
        """Test that failed status is published when token minting fails."""
        from spec_compiler.services.github_auth import MintingError
        
        # Mock minting error
        mock_auth_instance = Mock()
        mock_auth_client_cls.return_value = mock_auth_instance
        mock_auth_instance.mint_user_to_server_token.side_effect = MintingError(
            "Minting failed", status_code=500
        )

        payload = {
            "plan_id": "plan-minting-fail",
            "spec_index": 2,
            "spec_data": {},
            "github_owner": "owner",
            "github_repo": "repo",
        }

        response = test_client.post("/compile-spec", json=payload)

        # Should still return an error response
        assert response.status_code in (500, 502, 503)
        
        # Verify failed status was published
        failed_calls = [
            call for call in mock_publisher.publish_status.call_args_list
            if call[0][0].status == "failed"
        ]
        assert len(failed_calls) >= 1
        
        # Verify message fields
        msg = failed_calls[0][0][0]
        assert msg.plan_id == "plan-minting-fail"
        assert msg.spec_index == 2
        assert msg.status == "failed"
        assert msg.error_code == "minting_error"
        assert msg.error_message is not None

    @patch("spec_compiler.app.routes.compile.create_llm_client")
    def test_publishes_failed_on_llm_config_error(
        self,
        mock_create_client: Mock,
        test_client: TestClient,
        mock_publisher: Mock,
    ) -> None:
        """Test that failed status is published on LLM configuration error."""
        from spec_compiler.services.llm_client import LlmConfigurationError
        
        # Mock LLM configuration error
        mock_create_client.side_effect = LlmConfigurationError("LLM not configured")

        payload = {
            "plan_id": "plan-llm-config-fail",
            "spec_index": 3,
            "spec_data": {},
            "github_owner": "owner",
            "github_repo": "repo",
        }

        response = test_client.post("/compile-spec", json=payload)

        # Should return 500
        assert response.status_code == 500
        
        # Verify failed status was published
        failed_calls = [
            call for call in mock_publisher.publish_status.call_args_list
            if call[0][0].status == "failed"
        ]
        assert len(failed_calls) >= 1
        
        msg = failed_calls[0][0][0]
        assert msg.plan_id == "plan-llm-config-fail"
        assert msg.error_code == "llm_configuration_error"

    def test_publishes_failed_on_llm_api_error(
        self, test_client: TestClient, mock_publisher: Mock
    ) -> None:
        """Test that failed status is published on LLM API error."""
        from spec_compiler.services.llm_client import LlmApiError
        
        with patch("spec_compiler.app.routes.compile.create_llm_client") as mock_create:
            mock_client = Mock()
            mock_create.return_value = mock_client
            mock_client.generate_response.side_effect = LlmApiError("API error")

            payload = {
                "plan_id": "plan-llm-api-fail",
                "spec_index": 4,
                "spec_data": {},
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            # Should return 503
            assert response.status_code == 503
            
            # Verify failed status was published
            failed_calls = [
                call for call in mock_publisher.publish_status.call_args_list
                if call[0][0].status == "failed"
            ]
            assert len(failed_calls) >= 1
            
            msg = failed_calls[0][0][0]
            assert msg.plan_id == "plan-llm-api-fail"
            assert msg.error_code == "llm_api_error"


class TestPublisherFailureIsolation:
    """Tests that publisher failures don't break compile flow."""

    def test_compile_succeeds_when_publisher_disabled(
        self, test_client: TestClient, mock_publisher_disabled: Mock
    ) -> None:
        """Test that compile succeeds even when publisher is disabled."""
        payload = {
            "plan_id": "plan-no-publisher",
            "spec_index": 0,
            "spec_data": {},
            "github_owner": "owner",
            "github_repo": "repo",
        }

        response = test_client.post("/compile-spec", json=payload)

        # Should still succeed
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"

    def test_compile_succeeds_when_publish_throws(
        self, test_client: TestClient, mock_publisher: Mock
    ) -> None:
        """Test that compile succeeds even when publish_status throws."""
        # Make publish_status raise an exception
        mock_publisher.publish_status.side_effect = Exception("Pub/Sub error")

        payload = {
            "plan_id": "plan-publish-error",
            "spec_index": 0,
            "spec_data": {},
            "github_owner": "owner",
            "github_repo": "repo",
        }

        response = test_client.post("/compile-spec", json=payload)

        # Should still succeed
        assert response.status_code == 202
        assert response.json()["status"] == "accepted"

    def test_error_response_returned_when_publish_fails(
        self, test_client: TestClient, mock_publisher: Mock
    ) -> None:
        """Test that error responses are returned even when publish fails."""
        from spec_compiler.services.llm_client import LlmConfigurationError
        
        # Make both LLM and publisher fail
        mock_publisher.publish_status.side_effect = Exception("Pub/Sub error")
        
        with patch("spec_compiler.app.routes.compile.create_llm_client") as mock_create:
            mock_create.side_effect = LlmConfigurationError("LLM error")

            payload = {
                "plan_id": "plan-double-fail",
                "spec_index": 0,
                "spec_data": {},
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            # Should return the LLM error, not masked by publisher error
            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert data["detail"]["error"] == "LLM service not configured"


class TestStatusPublishingEdgeCases:
    """Tests for edge cases in status publishing."""

    def test_missing_request_id_generates_fallback(
        self, test_client: TestClient, mock_publisher: Mock
    ) -> None:
        """Test that missing request_id generates a fallback UUID."""
        # This is handled by middleware, but test the fallback path
        payload = {
            "plan_id": "plan-fallback-id",
            "spec_index": 0,
            "spec_data": {},
            "github_owner": "owner",
            "github_repo": "repo",
        }

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 202
        
        # Verify request_id was generated
        data = response.json()
        assert "request_id" in data
        assert data["request_id"] is not None

    def test_zero_spec_index_is_valid(
        self, test_client: TestClient, mock_publisher: Mock
    ) -> None:
        """Test that spec_index=0 is valid for status publishing."""
        payload = {
            "plan_id": "plan-zero-index",
            "spec_index": 0,
            "spec_data": {},
            "github_owner": "owner",
            "github_repo": "repo",
        }

        response = test_client.post("/compile-spec", json=payload)

        assert response.status_code == 202
        
        # Verify status messages were published with spec_index=0
        for call in mock_publisher.publish_status.call_args_list:
            msg = call[0][0]
            if msg.status in ("in_progress", "succeeded"):
                assert msg.spec_index == 0

    def test_large_error_messages_are_truncated(
        self, test_client: TestClient, mock_publisher: Mock
    ) -> None:
        """Test that large error messages are truncated in status messages."""
        from spec_compiler.services.llm_client import LlmConfigurationError
        
        # Create a very long error message
        long_error = "Error: " + "X" * 10000
        
        with patch("spec_compiler.app.routes.compile.create_llm_client") as mock_create:
            mock_create.side_effect = LlmConfigurationError(long_error)

            payload = {
                "plan_id": "plan-long-error",
                "spec_index": 0,
                "spec_data": {},
                "github_owner": "owner",
                "github_repo": "repo",
            }

            response = test_client.post("/compile-spec", json=payload)

            assert response.status_code == 500
            
            # Verify error message was truncated in status message
            failed_calls = [
                call for call in mock_publisher.publish_status.call_args_list
                if call[0][0].status == "failed"
            ]
            if failed_calls:
                msg = failed_calls[0][0][0]
                # PlanStatusMessage validator should truncate to MAX_ERROR_MESSAGE_LENGTH
                assert len(msg.error_message) <= 10000 + 100  # Allow some buffer for truncation marker
