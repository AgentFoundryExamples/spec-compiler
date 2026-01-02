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
Tests for PlanSchedulerPublisher service.

Validates the Pub/Sub publisher including configuration validation,
publish logic, retry behavior, and error handling.
"""

import os
import tempfile
from unittest.mock import Mock, patch

import pytest
from google.api_core import exceptions as gcp_exceptions

from spec_compiler.models.plan_status import PlanStatusMessage
from spec_compiler.services.plan_scheduler_publisher import (
    ConfigurationError,
    PlanSchedulerPublisher,
)


class TestPlanSchedulerPublisherConfiguration:
    """Tests for publisher configuration and initialization."""

    def test_missing_gcp_project_id_raises_error(self) -> None:
        """Test that missing GCP_PROJECT_ID raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            PlanSchedulerPublisher(
                gcp_project_id=None,
                topic_name="test-topic",
            )
        assert "GCP_PROJECT_ID" in str(exc_info.value)

    def test_empty_gcp_project_id_raises_error(self) -> None:
        """Test that empty GCP_PROJECT_ID raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            PlanSchedulerPublisher(
                gcp_project_id="   ",
                topic_name="test-topic",
            )
        assert "GCP_PROJECT_ID" in str(exc_info.value)

    def test_missing_topic_name_raises_error(self) -> None:
        """Test that missing topic_name raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            PlanSchedulerPublisher(
                gcp_project_id="test-project",
                topic_name=None,
            )
        assert "PUBSUB_TOPIC_PLAN_STATUS" in str(exc_info.value)

    def test_empty_topic_name_raises_error(self) -> None:
        """Test that empty topic_name raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            PlanSchedulerPublisher(
                gcp_project_id="test-project",
                topic_name="   ",
            )
        assert "PUBSUB_TOPIC_PLAN_STATUS" in str(exc_info.value)

    def test_nonexistent_credentials_path_raises_error(self) -> None:
        """Test that nonexistent credentials path raises ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            PlanSchedulerPublisher(
                gcp_project_id="test-project",
                topic_name="test-topic",
                credentials_path="/nonexistent/path/to/credentials.json",
            )
        assert "not found" in str(exc_info.value).lower()
        assert "PUBSUB_CREDENTIALS_PATH" in str(exc_info.value)

    def test_empty_credentials_file_raises_error(self) -> None:
        """Test that empty credentials file raises ConfigurationError."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            temp_path = f.name
            # File is created but empty

        try:
            with pytest.raises(ConfigurationError) as exc_info:
                PlanSchedulerPublisher(
                    gcp_project_id="test-project",
                    topic_name="test-topic",
                    credentials_path=temp_path,
                )
            assert "empty" in str(exc_info.value).lower()
        finally:
            os.unlink(temp_path)

    def test_directory_as_credentials_path_raises_error(self) -> None:
        """Test that directory path raises ConfigurationError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with pytest.raises(ConfigurationError) as exc_info:
                PlanSchedulerPublisher(
                    gcp_project_id="test-project",
                    topic_name="test-topic",
                    credentials_path=temp_dir,
                )
            assert "not found" in str(exc_info.value).lower()

    @patch("spec_compiler.services.plan_scheduler_publisher.pubsub_v1.PublisherClient")
    def test_successful_initialization_with_client_injection(
        self, mock_publisher_client: Mock
    ) -> None:
        """Test successful initialization with dependency-injected client."""
        mock_client = Mock()
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
        )

        assert publisher.gcp_project_id == "test-project"
        assert publisher.topic_name == "test-topic"
        assert publisher.client == mock_client
        assert publisher.topic_path == "projects/test-project/topics/test-topic"

    @patch("spec_compiler.services.plan_scheduler_publisher.pubsub_v1.PublisherClient")
    def test_initialization_without_credentials_uses_adc(
        self, mock_publisher_client: Mock
    ) -> None:
        """Test initialization without credentials uses Application Default Credentials."""
        mock_instance = Mock()
        mock_instance.topic_path.return_value = "projects/test-project/topics/test-topic"
        mock_publisher_client.return_value = mock_instance

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
        )

        # Verify PublisherClient was called without credentials argument
        mock_publisher_client.assert_called_once_with()
        assert publisher.client == mock_instance


class TestPlanSchedulerPublisherPublish:
    """Tests for publish_status method."""

    def test_successful_publish(self) -> None:
        """Test successful message publish."""
        mock_client = Mock()
        mock_future = Mock()
        mock_future.result.return_value = "message-id-123"
        mock_client.publish.return_value = mock_future
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
        )

        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )

        publisher.publish_status(message)

        # Verify publish was called
        mock_client.publish.assert_called_once()
        call_args = mock_client.publish.call_args
        assert call_args[0][0] == "projects/test-project/topics/test-topic"
        assert isinstance(call_args[0][1], bytes)  # Message bytes
        assert call_args[1]["ordering_key"] == "plan-123"

        # Verify future.result was called with timeout
        mock_future.result.assert_called_once()
        assert "timeout" in mock_future.result.call_args[1]

    def test_custom_ordering_key(self) -> None:
        """Test publish with custom ordering key."""
        mock_client = Mock()
        mock_future = Mock()
        mock_future.result.return_value = "message-id-123"
        mock_client.publish.return_value = mock_future
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
        )

        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )

        publisher.publish_status(message, ordering_key="custom-key")

        call_args = mock_client.publish.call_args
        assert call_args[1]["ordering_key"] == "custom-key"

    def test_retry_on_transient_error(self) -> None:
        """Test that transient errors trigger retry."""
        mock_client = Mock()
        mock_future_fail = Mock()
        mock_future_fail.result.side_effect = gcp_exceptions.ServiceUnavailable("Service down")
        mock_future_success = Mock()
        mock_future_success.result.return_value = "message-id-123"

        # First call fails, second succeeds
        mock_client.publish.side_effect = [mock_future_fail, mock_future_success]
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
            max_retries=2,
        )

        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )

        # Should succeed after retry
        publisher.publish_status(message)

        # Verify publish was called twice
        assert mock_client.publish.call_count == 2

    def test_exhausted_retries_raises_exception(self) -> None:
        """Test that exhausted retries raises exception."""
        mock_client = Mock()
        mock_future = Mock()
        mock_future.result.side_effect = gcp_exceptions.ServiceUnavailable("Service down")
        mock_client.publish.return_value = mock_future
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
            max_retries=2,
        )

        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )

        with pytest.raises(gcp_exceptions.ServiceUnavailable):
            publisher.publish_status(message)

        # Verify publish was called max_retries + 1 times
        assert mock_client.publish.call_count == 3

    def test_permanent_error_no_retry(self) -> None:
        """Test that permanent errors are not retried."""
        mock_client = Mock()
        mock_future = Mock()
        # PermissionDenied is a permanent error
        mock_future.result.side_effect = gcp_exceptions.PermissionDenied("Access denied")
        mock_client.publish.return_value = mock_future
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
            max_retries=2,
        )

        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )

        with pytest.raises(gcp_exceptions.PermissionDenied):
            publisher.publish_status(message)

        # Verify publish was called only once (no retries)
        assert mock_client.publish.call_count == 1

    def test_timeout_triggers_retry(self) -> None:
        """Test that timeout errors trigger retry."""
        mock_client = Mock()
        mock_future_timeout = Mock()
        mock_future_timeout.result.side_effect = gcp_exceptions.DeadlineExceeded("Timeout")
        mock_future_success = Mock()
        mock_future_success.result.return_value = "message-id-123"

        # First call times out, second succeeds
        mock_client.publish.side_effect = [mock_future_timeout, mock_future_success]
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
            max_retries=2,
        )

        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )

        # Should succeed after retry
        publisher.publish_status(message)

        # Verify publish was called twice
        assert mock_client.publish.call_count == 2

    @patch("spec_compiler.services.plan_scheduler_publisher.time.sleep")
    def test_backoff_delay_increases_exponentially(self, mock_sleep: Mock) -> None:
        """Test that backoff delay increases exponentially with jitter."""
        mock_client = Mock()
        mock_future = Mock()
        mock_future.result.side_effect = [
            gcp_exceptions.ServiceUnavailable("Down"),
            gcp_exceptions.ServiceUnavailable("Down"),
            Mock(return_value="message-id-123"),  # Third attempt succeeds
        ]
        mock_client.publish.return_value = mock_future
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
            max_retries=3,
        )

        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )

        publisher.publish_status(message)

        # Verify sleep was called with increasing delays
        assert mock_sleep.call_count == 2
        delays = [call[0][0] for call in mock_sleep.call_args_list]
        # First delay should be less than second (exponential backoff)
        assert delays[0] < delays[1]
        # Delays should be reasonable (with jitter)
        assert all(0 < delay < 10 for delay in delays)


class TestPlanSchedulerPublisherHelpers:
    """Tests for helper methods."""

    def test_is_transient_error_service_unavailable(self) -> None:
        """Test that ServiceUnavailable is identified as transient."""
        mock_client = Mock()
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
        )

        error = gcp_exceptions.ServiceUnavailable("Service down")
        assert publisher._is_transient_error(error) is True

    def test_is_transient_error_internal_server_error(self) -> None:
        """Test that InternalServerError is identified as transient."""
        mock_client = Mock()
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
        )

        error = gcp_exceptions.InternalServerError("Server error")
        assert publisher._is_transient_error(error) is True

    def test_is_transient_error_permission_denied(self) -> None:
        """Test that PermissionDenied is not transient."""
        mock_client = Mock()
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
        )

        error = gcp_exceptions.PermissionDenied("Access denied")
        assert publisher._is_transient_error(error) is False

    def test_calculate_backoff_delay(self) -> None:
        """Test backoff delay calculation."""
        mock_client = Mock()
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
        )

        delay_0 = publisher._calculate_backoff_delay(0)
        delay_1 = publisher._calculate_backoff_delay(1)
        delay_2 = publisher._calculate_backoff_delay(2)

        # Delays should increase
        assert delay_0 < delay_1 < delay_2
        # Delays should be within reasonable bounds
        assert 0 < delay_0 < 2
        assert 0 < delay_1 < 4
        assert 0 < delay_2 < 6

    def test_close_publisher(self) -> None:
        """Test closing the publisher."""
        mock_client = Mock()
        mock_transport = Mock()
        mock_client.transport = mock_transport
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
        )

        publisher.close()

        # Verify transport.close was called
        mock_transport.close.assert_called_once()
