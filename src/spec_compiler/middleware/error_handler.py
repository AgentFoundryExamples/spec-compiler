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
"""

import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse


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

            # Create safe error message (don't leak internal details)
            safe_message = f"An internal error occurred. Please contact support with request_id: {request_id}"

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
            char for char in idempotency_key if char.isprintable() and not char.isspace() or char == " "
        )

        return idempotency_key.strip() or None
