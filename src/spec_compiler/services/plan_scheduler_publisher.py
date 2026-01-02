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
Plan Scheduler Publisher service for Google Cloud Pub/Sub.

Provides a reusable PlanSchedulerPublisher that serializes PlanStatusMessage
payloads and publishes them to Google Cloud Pub/Sub with retry-aware error handling.
"""

import random
import time
from pathlib import Path

import structlog
from google.api_core import exceptions as gcp_exceptions
from google.cloud import pubsub_v1  # type: ignore[import-untyped]
from google.oauth2 import service_account

from spec_compiler.models.plan_status import PlanStatusMessage

logger = structlog.get_logger(__name__)

# Retry configuration constants
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 0.5  # seconds
DEFAULT_MAX_DELAY = 5.0  # seconds
DEFAULT_PUBLISH_TIMEOUT = 10.0  # seconds

# Global publisher instance (initialized on first use)
_publisher: "PlanSchedulerPublisher | None" = None
_publisher_init_failed = False


def get_publisher() -> "PlanSchedulerPublisher | None":
    """
    Get or create the singleton PlanSchedulerPublisher instance.

    Returns None if publisher configuration is invalid or initialization failed.
    Logs errors but doesn't raise to prevent blocking the calling code.

    This function provides a centralized way to access the publisher across
    the application (compile endpoint, error handler middleware, etc.).

    Returns:
        PlanSchedulerPublisher instance or None if unavailable
    """
    global _publisher, _publisher_init_failed

    # Return None if we already know initialization failed
    if _publisher_init_failed:
        return None

    # Return existing publisher if already initialized
    if _publisher is not None:
        return _publisher

    # Try to initialize publisher
    try:
        from spec_compiler.config import settings

        _publisher = PlanSchedulerPublisher(
            gcp_project_id=settings.gcp_project_id,
            topic_name=settings.pubsub_topic_plan_status,
            credentials_path=settings.pubsub_credentials_path,
        )
        logger.info("PlanSchedulerPublisher initialized successfully")
        return _publisher
    except ConfigurationError as e:
        # Log configuration error but don't fail
        logger.warning(
            "PlanSchedulerPublisher not configured, status publishing disabled",
            error=str(e),
        )
        _publisher_init_failed = True
        return None
    except Exception as e:
        # Log unexpected error but don't fail
        logger.error(
            "Failed to initialize PlanSchedulerPublisher, status publishing disabled",
            error=str(e),
            error_type=type(e).__name__,
        )
        _publisher_init_failed = True
        return None


class ConfigurationError(Exception):
    """
    Raised when publisher configuration is invalid or missing.

    This includes missing environment variables, invalid credentials paths,
    or other configuration issues that prevent the publisher from initializing.
    """

    pass


class PlanSchedulerPublisher:
    """
    Publisher for plan status updates to Google Cloud Pub/Sub.

    This service encapsulates Google Pub/Sub client usage for publishing
    PlanStatusMessage payloads. It provides retry logic with exponential
    backoff and jitter for transient failures, and structured logging
    for observability.

    The publisher is designed to be:
    - Non-blocking: Uses async futures for publishing
    - Testable: Accepts dependency-injected clients
    - Configurable: Honors environment-based configuration
    - Extensible: Can be adapted for future status types

    Example usage:
        ```python
        from spec_compiler.services import PlanSchedulerPublisher
        from spec_compiler.models import PlanStatusMessage
        from spec_compiler.config import settings

        # Initialize publisher
        publisher = PlanSchedulerPublisher(
            gcp_project_id=settings.gcp_project_id,
            topic_name=settings.pubsub_topic_plan_status,
            credentials_path=settings.pubsub_credentials_path,
        )

        # Publish a status update
        message = PlanStatusMessage(
            plan_id="plan-123",
            spec_index=0,
            status="in_progress",
            request_id="req-456",
        )
        publisher.publish_status(message)
        ```

    Extensibility for future status types:
        To add support for additional status message types (e.g., BuildStatusMessage):
        1. Define a new model similar to PlanStatusMessage with to_json_bytes() method
        2. Add a new publish method (e.g., publish_build_status) that follows the
           same pattern as publish_status
        3. Consider extracting common retry/timeout logic into a private _publish_with_retry
           method to reduce code duplication

    Attributes:
        gcp_project_id: GCP project ID where the topic resides
        topic_name: Pub/Sub topic name for publishing
        client: Google Pub/Sub PublisherClient instance
        topic_path: Full topic path (projects/{project}/topics/{topic})
    """

    def __init__(
        self,
        gcp_project_id: str | None = None,
        topic_name: str | None = None,
        credentials_path: str | None = None,
        client: pubsub_v1.PublisherClient | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        publish_timeout: float = DEFAULT_PUBLISH_TIMEOUT,
    ):
        """
        Initialize the PlanSchedulerPublisher.

        Args:
            gcp_project_id: GCP project ID. Required unless client is provided.
            topic_name: Pub/Sub topic name. Required unless client is provided.
            credentials_path: Optional path to GCP service account credentials JSON file.
                If not provided, uses Application Default Credentials.
            client: Optional pre-configured PublisherClient for dependency injection.
                If provided, gcp_project_id and topic_name must still be provided for
                constructing the topic path.
            max_retries: Maximum number of retry attempts for transient failures.
            publish_timeout: Timeout in seconds for each publish attempt.

        Raises:
            ConfigurationError: If required configuration is missing or invalid.
        """
        self.max_retries = max_retries
        self.publish_timeout = publish_timeout

        # Validate required configuration
        if not gcp_project_id or not gcp_project_id.strip():
            raise ConfigurationError(
                "GCP_PROJECT_ID is required for PlanSchedulerPublisher. "
                "Set the GCP_PROJECT_ID environment variable."
            )

        if not topic_name or not topic_name.strip():
            raise ConfigurationError(
                "PUBSUB_TOPIC_PLAN_STATUS is required for PlanSchedulerPublisher. "
                "Set the PUBSUB_TOPIC_PLAN_STATUS environment variable."
            )

        self.gcp_project_id = gcp_project_id
        self.topic_name = topic_name

        # Initialize or use provided client
        if client is not None:
            self.client = client
            logger.info("Using dependency-injected Pub/Sub client")
        else:
            self.client = self._initialize_client(credentials_path)

        # Construct topic path
        self.topic_path = self.client.topic_path(self.gcp_project_id, self.topic_name)

        logger.info(
            "PlanSchedulerPublisher initialized",
            gcp_project_id=self.gcp_project_id,
            topic_name=self.topic_name,
            topic_path=self.topic_path,
            max_retries=self.max_retries,
        )

    def _initialize_client(self, credentials_path: str | None) -> pubsub_v1.PublisherClient:
        """
        Initialize the Google Cloud Pub/Sub PublisherClient.

        Args:
            credentials_path: Optional path to credentials JSON file

        Returns:
            Initialized PublisherClient

        Raises:
            ConfigurationError: If credentials path is invalid
        """
        try:
            if credentials_path:
                # Validate credentials path
                cred_path = Path(credentials_path)
                if not cred_path.is_file():
                    error_msg = (
                        f"Pub/Sub credentials file not found at: {credentials_path}. "
                        f"Please verify PUBSUB_CREDENTIALS_PATH points to a valid JSON file, "
                        f"or remove it to use Application Default Credentials."
                    )
                    logger.error(
                        "Invalid credentials path",
                        credentials_path=credentials_path,
                        exists=cred_path.exists(),
                        is_file=False,
                    )
                    raise ConfigurationError(error_msg)

                if cred_path.stat().st_size == 0:
                    error_msg = (
                        f"Pub/Sub credentials file is empty: {credentials_path}. "
                        f"Please provide a valid service account JSON file."
                    )
                    logger.error("Empty credentials file", credentials_path=credentials_path)
                    raise ConfigurationError(error_msg)

                logger.info(
                    "Initializing Pub/Sub client with credentials file",
                    credentials_path=credentials_path,
                )
                # Use credentials from file
                credentials = service_account.Credentials.from_service_account_file(str(cred_path))
                return pubsub_v1.PublisherClient(credentials=credentials)
            else:
                logger.info(
                    "Initializing Pub/Sub client with Application Default Credentials (ADC)"
                )
                # Use Application Default Credentials
                return pubsub_v1.PublisherClient()

        except Exception as e:
            if isinstance(e, ConfigurationError):
                raise
            error_msg = (
                f"Failed to initialize Pub/Sub client: {e}. "
                f"Check your credentials configuration and ensure you have proper GCP permissions."
            )
            logger.error("Client initialization failed", error=str(e), error_type=type(e).__name__)
            raise ConfigurationError(error_msg) from e

    def _calculate_backoff_delay(self, attempt: int) -> float:
        """
        Calculate exponential backoff delay with jitter.

        Uses additive jitter rather than multiplicative to provide better
        distribution of retry attempts and avoid thundering herd issues.

        Args:
            attempt: Current retry attempt number (0-indexed)

        Returns:
            Delay in seconds
        """
        # Exponential backoff: delay = base_delay * (2 ^ attempt)
        delay = DEFAULT_BASE_DELAY * (2**attempt)
        # Cap at max delay
        delay = min(delay, DEFAULT_MAX_DELAY)
        # Add jitter: a random fraction of the delay (up to 10%)
        jitter = random.uniform(0, delay * 0.1)
        jittered_delay: float = delay + jitter
        return jittered_delay

    def publish_status(
        self,
        plan_status: PlanStatusMessage,
        ordering_key: str | None = None,
    ) -> None:
        """
        Publish a plan status message to Pub/Sub with retry logic.

        This method serializes the PlanStatusMessage and publishes it to the
        configured Pub/Sub topic. It handles transient failures with exponential
        backoff and jitter, and provides structured logging for observability.

        The method uses non-blocking publish futures but waits for completion
        with a timeout to ensure ordering guarantees when needed.

        Args:
            plan_status: The PlanStatusMessage to publish
            ordering_key: Optional ordering key for message ordering.
                If not provided, uses plan_id as the ordering key to ensure
                messages for the same plan are processed in order.

        Raises:
            Exception: If all retry attempts are exhausted or a permanent failure occurs.
                The caller is responsible for handling these failures appropriately.
        """
        # Use plan_id as ordering key by default
        if ordering_key is None:
            ordering_key = plan_status.plan_id

        # Serialize message
        message_bytes = plan_status.to_json_bytes()

        logger.info(
            "Publishing plan status message",
            plan_id=plan_status.plan_id,
            spec_index=plan_status.spec_index,
            status=plan_status.status,
            request_id=plan_status.request_id,
            ordering_key=ordering_key,
            message_size_bytes=len(message_bytes),
        )

        for attempt in range(self.max_retries + 1):
            try:
                # Publish message
                future = self.client.publish(
                    self.topic_path,
                    message_bytes,
                    ordering_key=ordering_key,
                )

                # Wait for publish to complete with timeout
                message_id = future.result(timeout=self.publish_timeout)

                logger.info(
                    "Successfully published plan status message",
                    plan_id=plan_status.plan_id,
                    spec_index=plan_status.spec_index,
                    status=plan_status.status,
                    request_id=plan_status.request_id,
                    message_id=message_id,
                    attempt=attempt + 1,
                )
                return

            except gcp_exceptions.GoogleAPICallError as e:
                # Check if error is transient
                is_transient = self._is_transient_error(e)

                logger.warning(
                    "Pub/Sub publish failed",
                    plan_id=plan_status.plan_id,
                    spec_index=plan_status.spec_index,
                    request_id=plan_status.request_id,
                    attempt=attempt + 1,
                    max_retries=self.max_retries + 1,
                    error=str(e),
                    error_type=type(e).__name__,
                    is_transient=is_transient,
                )

                # Don't retry permanent errors
                if not is_transient:
                    logger.error(
                        "Permanent Pub/Sub error, not retrying",
                        plan_id=plan_status.plan_id,
                        error=str(e),
                    )
                    raise

                # Check if we have retries left
                if attempt < self.max_retries:
                    delay = self._calculate_backoff_delay(attempt)
                    logger.info(
                        "Retrying after backoff",
                        plan_id=plan_status.plan_id,
                        attempt=attempt + 1,
                        delay_seconds=delay,
                    )
                    time.sleep(delay)
                else:
                    logger.error(
                        "All retry attempts exhausted for plan status publish",
                        plan_id=plan_status.plan_id,
                        spec_index=plan_status.spec_index,
                        request_id=plan_status.request_id,
                        total_attempts=attempt + 1,
                    )
                    raise

            except Exception as e:
                # Any non-GoogleAPICallError is unexpected and should not be retried
                logger.error(
                    "Unexpected error publishing to Pub/Sub",
                    plan_id=plan_status.plan_id,
                    spec_index=plan_status.spec_index,
                    request_id=plan_status.request_id,
                    attempt=attempt + 1,
                    error=str(e),
                    error_type=type(e).__name__,
                )
                raise

        # This should only be reached if max_retries is exhausted with transient errors
        # The loop should have raised the exception on the last attempt
        raise Exception(
            f"Failed to publish message after {self.max_retries + 1} attempts for "
            f"plan_id={plan_status.plan_id}, request_id={plan_status.request_id}"
        )

    def _is_transient_error(self, error: Exception) -> bool:
        """
        Determine if an error is transient and should be retried.

        Args:
            error: The exception to check

        Returns:
            True if the error is transient, False otherwise
        """
        # Common transient error codes
        transient_error_types = (
            gcp_exceptions.ServiceUnavailable,
            gcp_exceptions.InternalServerError,
            gcp_exceptions.TooManyRequests,
            gcp_exceptions.DeadlineExceeded,
            gcp_exceptions.Aborted,
        )

        return isinstance(error, transient_error_types)

    def close(self) -> None:
        """
        Close the Pub/Sub client and release resources.

        This should be called when the publisher is no longer needed,
        typically during application shutdown.

        Note: This method does not wait for in-flight publish operations to
        complete. If the publisher is closed while messages are being published,
        those operations may fail or be left in an inconsistent state. To ensure
        all messages are published before closing, callers should track publish
        futures and wait for them to complete before calling close().

        For graceful shutdown with pending publishes:
        1. Stop accepting new publish requests
        2. Wait for all pending publish futures to complete
        3. Call close() to release resources
        """
        if self.client:
            logger.info("Closing Pub/Sub client")
            # PublisherClient doesn't have an explicit close in older versions,
            # but we can try to stop the client gracefully
            try:
                # In newer versions, there might be a transport.close()
                if hasattr(self.client, "transport") and hasattr(self.client.transport, "close"):
                    self.client.transport.close()
            except Exception as e:
                logger.warning("Error closing Pub/Sub client", error=str(e))
