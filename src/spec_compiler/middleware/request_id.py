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
Request ID middleware for correlation and tracing.

Propagates or generates X-Request-Id header for request tracking.
"""

import uuid

import structlog
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from spec_compiler.config import settings


class RequestIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to propagate or generate request IDs.

    - Extracts request ID from incoming header (default: X-Request-Id)
    - Generates a new UUID if header is missing or malformed
    - Adds request ID to response headers
    - Binds request ID to logging context for correlation
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """
        Process request and add request ID to context.

        Args:
            request: Incoming HTTP request
            call_next: Next middleware or endpoint handler

        Returns:
            HTTP response with request ID header
        """
        # Extract or generate request ID
        request_id = request.headers.get(settings.request_id_header)

        # Validate and sanitize request ID
        if not request_id or len(request_id) > 100:
            request_id = str(uuid.uuid4())
        else:
            try:
                # Validate that the provided ID is a UUID.
                # If not, generate a new one to prevent injection of malformed IDs.
                uuid.UUID(request_id)
            except ValueError:
                request_id = str(uuid.uuid4())

        # Bind request ID to logging context
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Store in request state for access in route handlers
        request.state.request_id = request_id

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers[settings.request_id_header] = request_id

        return response
