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
Error handling middleware for uniform error responses.

Captures unhandled exceptions and returns structured JSON error responses.
Also publishes failed status messages when plan context is available.
"""

import json
import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from spec_compiler.models.plan_status import PlanStatusMessage
from spec_compiler.services.plan_scheduler_publisher import (
    ConfigurationError,
    PlanSchedulerPublisher,
)

# Global publisher instance (initialized on first use)
_publisher: PlanSchedulerPublisher | None = None
_publisher_init_failed = False


def get_publisher() -> PlanSchedulerPublisher | None:
    """
    Get or create the PlanSchedulerPublisher instance.

    Returns None if publisher configuration is invalid or initialization failed.
    Logs errors but doesn't raise to prevent blocking error handling.
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
        logger = structlog.get_logger(__name__)
        logger.info("PlanSchedulerPublisher initialized successfully for error handler")
        return _publisher
    except ConfigurationError:
        # Log configuration error but don't fail
        _publisher_init_failed = True
        return None
    except Exception:
        # Log unexpected error but don't fail
        _publisher_init_failed = True
        return None


def publish_failed_status_safe(
    plan_id: str,
    spec_index: int,
    request_id: str,
    error_message: str,
) -> None:
    """
    Safely publish a failed status message, catching and logging any errors.

    This function ensures that publisher failures never prevent error responses.

    Args:
        plan_id: Plan identifier
        spec_index: Spec index within the plan
        request_id: Request correlation ID
        error_message: Error message describing the failure
    """
    publisher = get_publisher()
    if publisher is None:
        return

    try:
        message = PlanStatusMessage(
            plan_id=plan_id,
            spec_index=spec_index,
            status="failed",
            request_id=request_id,
            error_code="unhandled_exception",
            error_message=error_message[:1000],  # Truncate for safety
        )
        publisher.publish_status(message)
    except Exception:
        # Silently fail - we're already in error handling
        pass


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle unhandled exceptions and return uniform error responses.

    - Captures unhandled exceptions during request processing
    - Returns HTTP 500 with structured JSON: { "error": "internal_error", "request_id": str, "message": str }
    - Logs full stack traces for debugging
    - Handles optional Idempotency-Key header (logs and echoes back)
    - Reuses existing request_id if already set by RequestIdMiddleware
    """

    # Maximum length for idempotency key to prevent abuse
    MAX_IDEMPOTENCY_KEY_LENGTH = 255

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Process request and handle any unhandled exceptions.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response (either from handler or error response)
        """
        logger = structlog.get_logger(__name__)

        # Extract and sanitize optional Idempotency-Key header
        idempotency_key = self._extract_idempotency_key(request)
        if idempotency_key:
            # Bind to logging context for correlation
            structlog.contextvars.bind_contextvars(idempotency_key=idempotency_key)
            logger.debug("Idempotency-Key received", idempotency_key=idempotency_key)

        # Log request start
        logger.info(
            "Request started",
            method=request.method,
            path=request.url.path,
            client_host=request.client.host if request.client else None,
        )

        try:
            # Process request through the rest of the middleware chain
            response = await call_next(request)

            # Log request completion
            logger.info(
                "Request completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
            )

            # Echo idempotency key in response header if it was provided
            if idempotency_key:
                response.headers["Idempotency-Key"] = idempotency_key

            return response

        except Exception as exc:
            # Get request_id from request state (set by RequestIdMiddleware)
            # Generate a fallback UUID if somehow missing
            request_id = getattr(request.state, "request_id", None)
            if not request_id:
                request_id = str(uuid.uuid4())
                logger.warning(
                    "request_id missing from request.state, generated fallback",
                    fallback_request_id=request_id,
                )

            # Log the full exception with stack trace
            logger.error(
                "Unhandled exception during request processing",
                exc_info=exc,
                exception_type=type(exc).__name__,
                exception_message=str(exc),
                request_id=request_id,
                method=request.method,
                path=request.url.path,
            )

            # Try to extract plan context from request body for status publishing
            plan_id = None
            spec_index = None
            try:
                # Attempt to read and parse body
                if request.method == "POST" and request.url.path == "/compile-spec":
                    # Try to get the body - it might have been consumed already
                    body = await request.body()
                    if body:
                        body_dict = json.loads(body)
                        plan_id = body_dict.get("plan_id")
                        spec_index = body_dict.get("spec_index")
            except Exception:
                # Silently fail - we're already in error handling
                pass

            # Publish failed status if we have plan context
            if plan_id and isinstance(spec_index, int):
                publish_failed_status_safe(
                    plan_id=plan_id,
                    spec_index=spec_index,
                    request_id=request_id,
                    error_message=f"Unhandled exception: {type(exc).__name__}: {str(exc)[:500]}",
                )

            # Create safe error message (don't leak internal details)
            safe_message = (
                f"An internal error occurred. Please contact support with request_id: {request_id}"
            )

            # Return structured error response
            error_response = JSONResponse(
                status_code=500,
                content={
                    "error": "internal_error",
                    "request_id": request_id,
                    "message": safe_message,
                },
            )

            # Echo idempotency key in error response if it was provided
            if idempotency_key:
                error_response.headers["Idempotency-Key"] = idempotency_key

            return error_response

    def _extract_idempotency_key(self, request: Request) -> str | None:
        """
        Extract and sanitize Idempotency-Key header from request.

        Args:
            request: Incoming HTTP request

        Returns:
            Sanitized idempotency key or None if not present/invalid
        """
        idempotency_key = request.headers.get("Idempotency-Key")

        if not idempotency_key:
            return None

        # Sanitize: truncate if too long
        if len(idempotency_key) > self.MAX_IDEMPOTENCY_KEY_LENGTH:
            logger = structlog.get_logger(__name__)
            logger.warning(
                "Idempotency-Key truncated due to excessive length",
                original_length=len(idempotency_key),
                max_length=self.MAX_IDEMPOTENCY_KEY_LENGTH,
            )
            idempotency_key = idempotency_key[: self.MAX_IDEMPOTENCY_KEY_LENGTH]

        # Sanitize: ensure it's safe for logging (remove control characters)
        idempotency_key = "".join(
            char
            for char in idempotency_key
            if char.isprintable() and not char.isspace() or char == " "
        )

        return idempotency_key.strip() or None
