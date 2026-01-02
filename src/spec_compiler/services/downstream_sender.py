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
Downstream Sender abstraction for forwarding compiled specs.

Provides a protocol for sending compiled specifications to downstream consumers,
with a default logging-only implementation that emits structured logs.
"""

from abc import ABC, abstractmethod
from threading import Lock
from typing import Any

import structlog

from spec_compiler.models.llm import LlmCompiledSpecOutput

logger = structlog.get_logger(__name__)


class DownstreamSenderError(Exception):
    """
    Base exception for downstream sender errors.

    Raised when general downstream sending operations fail, such as
    network errors, timeout errors, or unexpected failures during
    the send operation.
    """

    pass


class DownstreamValidationError(DownstreamSenderError):
    """
    Raised when context validation fails before sending.

    This exception is raised when required context fields are missing,
    empty, or contain invalid values (e.g., negative spec_index,
    whitespace-only plan_id). Validation errors prevent the send
    operation from proceeding and must be fixed by the caller.
    """

    pass


class DownstreamSender(ABC):
    """
    Abstract base class for downstream senders.

    Defines the interface for forwarding compiled specifications to downstream
    consumers (e.g., message queues, databases, APIs, or logging systems).
    """

    @abstractmethod
    def send_compiled_spec(
        self,
        output: LlmCompiledSpecOutput,
        context: dict[str, Any],
    ) -> None:
        """
        Send a compiled specification to the downstream consumer.

        Args:
            output: The compiled specification output from the LLM
            context: Context dictionary containing:
                - plan_id (str): Plan identifier (required)
                - spec_index (int): Specification index (required)
                - request_id (str): Request identifier (required)
                - github_owner (str): Repository owner (optional)
                - github_repo (str): Repository name (optional)

        Raises:
            DownstreamValidationError: If required context fields are missing
            DownstreamSenderError: If sending fails
        """
        pass


class DefaultDownstreamLoggerSender(DownstreamSender):
    """
    Default logging-only implementation of DownstreamSender.

    Emits structured logs with compiled spec metadata instead of making
    actual API calls or publishing to external systems. Useful for
    development, testing, and as a reference implementation.

    Logs include:
    - plan_id, spec_index, request_id
    - Repository metadata (owner, repo)
    - Placeholder downstream target URI
    - Skip status if configured to skip
    - Spec version and issue count from output
    """

    def __init__(self, downstream_target_uri: str | None = None, skip_send: bool = False):
        """
        Initialize the logging sender.

        Args:
            downstream_target_uri: Placeholder URI for the downstream target
            skip_send: If True, logs skip reason instead of attempting send
        """
        self.downstream_target_uri = downstream_target_uri or "placeholder://downstream/target"
        self.skip_send = skip_send
        logger.info(
            "DefaultDownstreamLoggerSender initialized",
            downstream_target_uri=self.downstream_target_uri,
            skip_send=self.skip_send,
        )

    def _validate_context(self, context: dict[str, Any]) -> None:
        """
        Validate that required context fields are present.

        Args:
            context: Context dictionary to validate

        Raises:
            DownstreamValidationError: If required fields are missing
        """
        required_fields = ["plan_id", "spec_index", "request_id"]
        missing_fields = [field for field in required_fields if field not in context]

        if missing_fields:
            raise DownstreamValidationError(
                f"Missing required context fields: {', '.join(missing_fields)}"
            )

        # Validate plan_id is not empty or whitespace
        plan_id = context.get("plan_id")
        if not plan_id or (isinstance(plan_id, str) and not plan_id.strip()):
            raise DownstreamValidationError("plan_id cannot be empty or whitespace")

        # Validate request_id is not empty or whitespace
        request_id = context.get("request_id")
        if not request_id or (isinstance(request_id, str) and not request_id.strip()):
            raise DownstreamValidationError("request_id cannot be empty or whitespace")

        # Validate spec_index is non-negative integer
        spec_index = context.get("spec_index")
        if not isinstance(spec_index, int) or spec_index < 0:
            raise DownstreamValidationError("spec_index must be a non-negative integer")

    def send_compiled_spec(
        self,
        output: LlmCompiledSpecOutput,
        context: dict[str, Any],
    ) -> None:
        """
        Log the compiled specification metadata with structured logging.

        Args:
            output: The compiled specification output from the LLM
            context: Context dictionary with plan_id, spec_index, request_id, etc.

        Raises:
            DownstreamValidationError: If required context fields are missing or invalid
        """
        # Validate required context fields
        self._validate_context(context)

        # Extract context fields
        plan_id = context["plan_id"]
        spec_index = context["spec_index"]
        request_id = context["request_id"]
        github_owner = context.get("github_owner")
        github_repo = context.get("github_repo")

        # Build log context
        log_context = {
            "plan_id": plan_id,
            "spec_index": spec_index,
            "request_id": request_id,
            "downstream_target": self.downstream_target_uri,
            "spec_version": output.version,
            "issue_count": len(output.issues),
        }

        # Add repository metadata if present
        if github_owner:
            log_context["github_owner"] = github_owner
        if github_repo:
            log_context["github_repo"] = github_repo

        # Log based on skip_send flag
        if self.skip_send:
            logger.info(
                "Downstream send skipped (SKIP_DOWNSTREAM_SEND=true)",
                **log_context,
                skip_reason="feature_flag_disabled",
            )
        else:
            logger.info(
                "Downstream send attempt (logging mode)",
                **log_context,
                send_status="executed",
            )


# Global sender instance (initialized on first use)
_sender: DownstreamSender | None = None
_sender_init_failed = False
_sender_lock = Lock()


def get_downstream_sender() -> DownstreamSender | None:
    """
    Get or create the singleton DownstreamSender instance.

    Returns None if sender configuration is invalid or initialization failed.
    Logs errors but doesn't raise to prevent blocking the calling code.

    This function provides a centralized way to access the sender across
    the application.

    Returns:
        DownstreamSender instance or None if unavailable
    """
    global _sender, _sender_init_failed

    # First check without a lock for performance
    if _sender is not None or _sender_init_failed:
        return _sender

    with _sender_lock:
        # Double-checked locking to prevent race conditions
        if _sender is not None or _sender_init_failed:
            return _sender

        # Try to initialize sender
        try:
            from spec_compiler.config import settings

            _sender = DefaultDownstreamLoggerSender(
                downstream_target_uri=settings.downstream_target_uri,
                skip_send=settings.skip_downstream_send,
            )
            logger.info("DownstreamSender initialized successfully")
            return _sender
        except Exception as e:
            # Log error but don't fail - downstream sending is optional
            logger.warning(
                "Failed to initialize DownstreamSender, downstream sending disabled",
                error=str(e),
                error_type=type(e).__name__,
            )
            _sender_init_failed = True
            return None
