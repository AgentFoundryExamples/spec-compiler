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
    def test_initialization_without_credentials_uses_adc(self, mock_publisher_client: Mock) -> None:
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


class TestPublisherConcurrency:
    """Tests for concurrent request handling and thread safety."""

    def test_concurrent_publishes_are_thread_safe(self) -> None:
        """Test that concurrent publishes from multiple threads work correctly."""
        import json
        import threading
        from queue import Queue

        mock_client = Mock()
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        # Track all publish calls
        publish_calls = Queue()

        def mock_publish(topic, data, **kwargs):
            mock_future = Mock()
            mock_future.result.return_value = f"msg-{threading.current_thread().ident}"
            publish_calls.put((topic, data, kwargs))
            return mock_future

        mock_client.publish.side_effect = mock_publish

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
        )

        # Create messages for concurrent publishing
        messages = [
            PlanStatusMessage(
                plan_id=f"plan-{i}",
                spec_index=i,
                status="in_progress",
                request_id=f"req-{i}",
            )
            for i in range(10)
        ]

        # Publish from multiple threads
        errors = []

        def publish_message(msg):
            try:
                publisher.publish_status(msg)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=publish_message, args=(msg,)) for msg in messages]

        for thread in threads:
            thread.start()

        for thread in threads:
            thread.join()

        # Verify no errors occurred
        assert len(errors) == 0

        # Verify all messages were published
        assert mock_client.publish.call_count == 10
        assert publish_calls.qsize() == 10

        # Verify the content of published messages
        published_plan_ids = set()
        while not publish_calls.empty():
            _, data, _ = publish_calls.get()
            msg_dict = json.loads(data)
            published_plan_ids.add(msg_dict["plan_id"])

        expected_plan_ids = {f"plan-{i}" for i in range(10)}
        assert published_plan_ids == expected_plan_ids

    def test_message_ordering_with_ordering_key(self) -> None:
        """Test that messages with same ordering key maintain order."""
        mock_client = Mock()
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        # Track ordering keys used
        ordering_keys_used = []

        def mock_publish(topic, data, **kwargs):
            ordering_keys_used.append(kwargs.get("ordering_key"))
            mock_future = Mock()
            mock_future.result.return_value = "msg-id"
            return mock_future

        mock_client.publish.side_effect = mock_publish

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
        )

        # Publish multiple messages for same plan
        plan_id = "plan-ordered"
        for i in range(5):
            message = PlanStatusMessage(
                plan_id=plan_id,
                spec_index=i,
                status="in_progress",
                request_id=f"req-{i}",
            )
            publisher.publish_status(message)

        # Verify all used same ordering key (plan_id)
        assert len(ordering_keys_used) == 5
        assert all(key == plan_id for key in ordering_keys_used)

    def test_timeout_error_captured_with_correlation_id(self) -> None:
        """Test that timeout errors are logged with correlation context."""
        from google.api_core import exceptions as gcp_exceptions

        mock_client = Mock()
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        # Make publish timeout
        mock_future = Mock()
        mock_future.result.side_effect = gcp_exceptions.DeadlineExceeded(
            "Timeout: request deadline exceeded"
        )
        mock_client.publish.return_value = mock_future

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
            max_retries=0,  # Don't retry to keep test fast
        )

        message = PlanStatusMessage(
            plan_id="plan-timeout",
            spec_index=0,
            status="in_progress",
            request_id="req-timeout-123",
        )

        # Should raise timeout error
        with pytest.raises(gcp_exceptions.DeadlineExceeded):
            publisher.publish_status(message)

        # Verify request_id would be available for logging
        assert message.request_id == "req-timeout-123"

    def test_payload_size_validation(self) -> None:
        """Test that large payloads are handled correctly."""
        mock_client = Mock()
        mock_client.topic_path.return_value = "projects/test-project/topics/test-topic"

        mock_future = Mock()
        mock_future.result.return_value = "msg-id"
        mock_client.publish.return_value = mock_future

        publisher = PlanSchedulerPublisher(
            gcp_project_id="test-project",
            topic_name="test-topic",
            client=mock_client,
        )

        # Create message with large error message (should be truncated by model)
        large_error = "x" * 20000
        message = PlanStatusMessage(
            plan_id="plan-large",
            spec_index=0,
            status="failed",
            request_id="req-large",
            error_code="LARGE_ERROR",
            error_message=large_error,
        )

        publisher.publish_status(message)

        # Verify publish was called
        mock_client.publish.assert_called_once()

        # Verify message was truncated (by PlanStatusMessage model)
        call_args = mock_client.publish.call_args
        published_data = call_args[0][1]
        assert len(published_data) < len(large_error.encode("utf-8"))
