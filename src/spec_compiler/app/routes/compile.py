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
Compile API endpoint.

Provides the main compile endpoint for processing specifications.
"""

import json
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status

from spec_compiler.config import settings
from spec_compiler.logging import get_logger
from spec_compiler.models import create_llm_response_stub
from spec_compiler.models.compile import CompileRequest, CompileResponse

router = APIRouter()
logger = get_logger(__name__)


@router.post(
    "/compile-spec",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CompileResponse,
    responses={
        202: {
            "description": "Request accepted for processing",
            "content": {
                "application/json": {
                    "example": {
                        "request_id": "550e8400-e29b-41d4-a716-446655440000",
                        "plan_id": "plan-abc123",
                        "spec_index": 0,
                        "status": "accepted",
                        "message": "Request accepted for processing",
                    }
                }
            },
        },
        413: {
            "description": "Request body too large",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Request body exceeds maximum size limit of 10485760 bytes"
                    }
                }
            },
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [
                            {
                                "loc": ["body", "plan_id"],
                                "msg": "Field cannot be empty or whitespace-only",
                                "type": "value_error",
                            }
                        ]
                    }
                }
            },
        },
    },
)
async def compile_spec(
    request: Request,
    compile_request: CompileRequest,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CompileResponse:
    """
    Compile a specification with LLM integration.

    Accepts a compile request, validates the payload, logs the operation,
    and returns a 202 Accepted response. Currently stubs out downstream
    LLM integration.

    Args:
        request: FastAPI request object (for accessing request_id from middleware)
        compile_request: The compile request payload
        idempotency_key: Optional idempotency key for client-side deduplication

    Returns:
        CompileResponse with request tracking information

    Raises:
        HTTPException: 413 if request body exceeds size limit
        HTTPException: 422 if validation fails (handled by FastAPI)
    """
    # Get request_id from middleware
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        # Fallback if middleware didn't set it (shouldn't happen)
        from spec_compiler.models import generate_request_id

        request_id = generate_request_id()

    # Check body size limit (FastAPI doesn't provide built-in body size check before parsing)
    # This is a defense-in-depth measure - in production, you'd also want nginx/load balancer limits
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            body_size = int(content_length)
            if body_size > settings.max_request_body_size_bytes:
                logger.warning(
                    "Request body size exceeds limit",
                    request_id=request_id,
                    body_size=body_size,
                    max_size=settings.max_request_body_size_bytes,
                )
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Request body exceeds maximum size limit of {settings.max_request_body_size_bytes} bytes",
                )
        except ValueError:
            # Invalid content-length header, let FastAPI handle it
            pass

    # Sanitize idempotency key for logging (prevent injection attacks)
    safe_idempotency_key = None
    if idempotency_key:
        # Limit length and strip dangerous characters
        safe_idempotency_key = idempotency_key[:100].strip()

    # Log receipt of compile request
    logger.info(
        "Compile request received",
        request_id=request_id,
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
        github_owner=compile_request.github_owner,
        github_repo=compile_request.github_repo,
        idempotency_key=safe_idempotency_key,
        spec_data_type=type(compile_request.spec_data).__name__,
        spec_data_size=len(json.dumps(compile_request.spec_data)),
    )

    # Generate placeholder LLM response envelope
    llm_response = create_llm_response_stub(
        request_id=request_id,
        status="pending",
        content="",
        metadata={
            "status": "stubbed",
            "details": "LLM call not yet implemented",
        },
    )

    # Log the stubbed LLM response as if dispatching downstream
    logger.info(
        "Generated stubbed LLM response envelope",
        request_id=request_id,
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
        llm_status=llm_response.status,
        llm_metadata=llm_response.metadata,
    )

    # Create and return response
    response = CompileResponse(
        request_id=request_id,
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
        status="accepted",
        message="Request accepted for processing",
    )

    logger.info(
        "Compile request accepted",
        request_id=request_id,
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
    )

    return response
