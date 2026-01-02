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
import re
from typing import Annotated

from fastapi import APIRouter, Header, HTTPException, Request, status

from spec_compiler.config import settings
from spec_compiler.logging import get_logger
from spec_compiler.models import RepoContextPayload, create_llm_response_stub
from spec_compiler.models.compile import CompileRequest, CompileResponse
from spec_compiler.services.github_auth import GitHubAuthClient, MintingError
from spec_compiler.services.github_repo import (
    GitHubFileError,
    GitHubRepoClient,
    InvalidJSONError,
    create_fallback_dependencies,
    create_fallback_file_summaries,
    create_fallback_tree,
)

router = APIRouter()
logger = get_logger(__name__)


def fetch_repo_context(
    owner: str,
    repo: str,
    token: str,
    request_id: str,
) -> RepoContextPayload:
    """
    Fetch repository context from GitHub analysis files.

    Attempts to fetch tree.json, dependencies.json, and file-summaries.json
    from .github/repo-analysis-output/. Falls back to placeholder data
    for any missing or malformed files.

    Args:
        owner: GitHub repository owner
        repo: GitHub repository name
        token: GitHub access token
        request_id: Request ID for logging

    Returns:
        RepoContextPayload with tree, dependencies, and file_summaries
    """
    repo_client = GitHubRepoClient()
    base_path = ".github/repo-analysis-output"

    # Initialize with fallback values
    tree_data = None
    dependencies_data = None
    file_summaries_data = None

    # Fetch tree.json
    try:
        tree_data = repo_client.get_json_file(
            owner=owner,
            repo=repo,
            path=f"{base_path}/tree.json",
            token=token,
        )
        logger.info(
            "repo_context_tree_success",
            request_id=request_id,
            owner=owner,
            repo=repo,
            tree_entries=len(tree_data.get("tree", [])) if isinstance(tree_data, dict) else 0,
        )
    except GitHubFileError as e:
        logger.warning(
            "repo_context_tree_error",
            request_id=request_id,
            owner=owner,
            repo=repo,
            error=str(e),
            status_code=e.status_code,
            using_fallback=True,
        )
        tree_data = {"tree": create_fallback_tree()}
    except InvalidJSONError as e:
        logger.warning(
            "repo_context_tree_invalid_json",
            request_id=request_id,
            owner=owner,
            repo=repo,
            error=str(e),
            using_fallback=True,
        )
        tree_data = {"tree": create_fallback_tree()}

    # Fetch dependencies.json
    try:
        dependencies_data = repo_client.get_json_file(
            owner=owner,
            repo=repo,
            path=f"{base_path}/dependencies.json",
            token=token,
        )
        logger.info(
            "repo_context_dependencies_success",
            request_id=request_id,
            owner=owner,
            repo=repo,
            dependency_count=len(dependencies_data.get("dependencies", []))
            if isinstance(dependencies_data, dict)
            else 0,
        )
    except GitHubFileError as e:
        logger.warning(
            "repo_context_dependencies_error",
            request_id=request_id,
            owner=owner,
            repo=repo,
            error=str(e),
            status_code=e.status_code,
            using_fallback=True,
        )
        dependencies_data = {"dependencies": create_fallback_dependencies()}
    except InvalidJSONError as e:
        logger.warning(
            "repo_context_dependencies_invalid_json",
            request_id=request_id,
            owner=owner,
            repo=repo,
            error=str(e),
            using_fallback=True,
        )
        dependencies_data = {"dependencies": create_fallback_dependencies()}

    # Fetch file-summaries.json
    try:
        file_summaries_data = repo_client.get_json_file(
            owner=owner,
            repo=repo,
            path=f"{base_path}/file-summaries.json",
            token=token,
        )
        logger.info(
            "repo_context_file_summaries_success",
            request_id=request_id,
            owner=owner,
            repo=repo,
            summary_count=len(file_summaries_data.get("summaries", []))
            if isinstance(file_summaries_data, dict)
            else 0,
        )
    except GitHubFileError as e:
        logger.warning(
            "repo_context_file_summaries_error",
            request_id=request_id,
            owner=owner,
            repo=repo,
            error=str(e),
            status_code=e.status_code,
            using_fallback=True,
        )
        file_summaries_data = {"summaries": create_fallback_file_summaries()}
    except InvalidJSONError as e:
        logger.warning(
            "repo_context_file_summaries_invalid_json",
            request_id=request_id,
            owner=owner,
            repo=repo,
            error=str(e),
            using_fallback=True,
        )
        file_summaries_data = {"summaries": create_fallback_file_summaries()}

    # Extract data with safe defaults
    tree = tree_data.get("tree", create_fallback_tree()) if tree_data else create_fallback_tree()
    dependencies = (
        dependencies_data.get("dependencies", create_fallback_dependencies())
        if dependencies_data
        else create_fallback_dependencies()
    )
    file_summaries = (
        file_summaries_data.get("summaries", create_fallback_file_summaries())
        if file_summaries_data
        else create_fallback_file_summaries()
    )

    # Ensure values are lists
    if not isinstance(tree, list):
        logger.warning(
            "repo_context_tree_not_list",
            request_id=request_id,
            owner=owner,
            repo=repo,
            actual_type=type(tree).__name__,
        )
        tree = create_fallback_tree()

    if not isinstance(dependencies, list):
        logger.warning(
            "repo_context_dependencies_not_list",
            request_id=request_id,
            owner=owner,
            repo=repo,
            actual_type=type(dependencies).__name__,
        )
        dependencies = create_fallback_dependencies()

    if not isinstance(file_summaries, list):
        logger.warning(
            "repo_context_file_summaries_not_list",
            request_id=request_id,
            owner=owner,
            repo=repo,
            actual_type=type(file_summaries).__name__,
        )
        file_summaries = create_fallback_file_summaries()

    return RepoContextPayload(
        tree=tree,
        dependencies=dependencies,
        file_summaries=file_summaries,
    )


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
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CompileResponse:
    """
    Compile a specification with LLM integration.

    Accepts a compile request, validates the payload, logs the operation,
    and returns a 202 Accepted response. Currently stubs out downstream
    LLM integration.

    Args:
        request: FastAPI request object (for accessing request_id and body)
        idempotency_key: Optional idempotency key for client-side deduplication

    Returns:
        CompileResponse with request tracking information

    Raises:
        HTTPException: 413 if request body exceeds size limit
        HTTPException: 422 if validation fails (handled by Pydantic)
    """
    # Get request_id from middleware
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        # Fallback if middleware didn't set it (shouldn't happen)
        from spec_compiler.models import generate_request_id

        request_id = generate_request_id()

    # Check body size limit BEFORE parsing to prevent memory exhaustion
    # This check happens before FastAPI/Pydantic parses the JSON body
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

    # Read and parse body manually after size check
    body_bytes = await request.body()
    try:
        body_dict = json.loads(body_bytes)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid JSON: {str(e)}",
        ) from None

    # Validate using Pydantic model
    try:
        compile_request = CompileRequest.model_validate(body_dict)
    except Exception as e:
        # Preserve Pydantic's validation error format
        from pydantic import ValidationError

        if isinstance(e, ValidationError):
            # Convert Pydantic errors to JSON-serializable format
            # Use the errors() method which returns a list of dicts
            errors = e.errors()
            # Ensure all error details are JSON serializable
            serializable_errors = []
            for error in errors:
                serializable_error = {
                    "loc": error.get("loc", []),
                    "msg": error.get("msg", ""),
                    "type": error.get("type", ""),
                }
                if "input" in error:
                    serializable_error["input"] = error["input"]
                if "ctx" in error:
                    # Ensure ctx is serializable
                    try:
                        json.dumps(error["ctx"])
                        serializable_error["ctx"] = error["ctx"]
                    except (TypeError, ValueError):
                        # Skip non-serializable ctx
                        pass
                serializable_errors.append(serializable_error)

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=serializable_errors,
            ) from None
        else:
            # For other exceptions, wrap in simple format
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from None

    # Sanitize idempotency key for logging (prevent log injection attacks)
    # Only allow alphanumeric characters, hyphens, and underscores
    safe_idempotency_key = None
    if idempotency_key:
        # Validate pattern: alphanumeric, hyphens, underscores only
        sanitized = re.sub(r"[^a-zA-Z0-9\-_]", "", idempotency_key)
        # Truncate to max length
        safe_idempotency_key = (
            sanitized[: settings.max_idempotency_key_length] if sanitized else None
        )

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

    # Initialize GitHub clients
    auth_client = GitHubAuthClient()

    # Mint GitHub token for repository access
    try:
        logger.info(
            "minting_token_start",
            request_id=request_id,
            owner=compile_request.github_owner,
            repo=compile_request.github_repo,
        )

        github_token = auth_client.mint_user_to_server_token(
            owner=compile_request.github_owner,
            repo=compile_request.github_repo,
        )

        logger.info(
            "minting_token_success",
            request_id=request_id,
            owner=compile_request.github_owner,
            repo=compile_request.github_repo,
            token_type=github_token.token_type,
            has_expiry=github_token.expires_at is not None,
        )

        token_str = github_token.access_token

    except MintingError as e:
        logger.error(
            "minting_token_failed",
            request_id=request_id,
            owner=compile_request.github_owner,
            repo=compile_request.github_repo,
            error=str(e),
            status_code=e.status_code,
            context=e.context,
        )

        # Map minting errors to appropriate HTTP status codes
        # Use 502 Bad Gateway for service communication failures
        # Use 503 Service Unavailable for temporary failures
        # Use 500 Internal Server Error for configuration issues
        if e.status_code is not None:
            # If we have an HTTP status from the minting service, use it to determine mapping
            if e.status_code >= 500:
                http_status = status.HTTP_503_SERVICE_UNAVAILABLE
                error_message = "Token minting service temporarily unavailable"
            elif e.status_code >= 400:
                http_status = status.HTTP_502_BAD_GATEWAY
                error_message = "Token minting service error"
            else:
                http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
                error_message = "Unexpected token minting error"
        elif "not configured" in str(e).lower():
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_message = "Token minting service not configured"
        else:
            http_status = status.HTTP_502_BAD_GATEWAY
            error_message = "Token minting service error"

        # Return structured error response with valid JSON
        raise HTTPException(
            status_code=http_status,
            detail={
                "error": error_message,
                "request_id": request_id,
                "plan_id": compile_request.plan_id,
                "spec_index": compile_request.spec_index,
                "message": "Unable to authenticate with GitHub. Please retry or contact support.",
            },
        )

    # Fetch repository context
    try:
        logger.info(
            "fetching_repo_context_start",
            request_id=request_id,
            owner=compile_request.github_owner,
            repo=compile_request.github_repo,
        )

        repo_context = fetch_repo_context(
            owner=compile_request.github_owner,
            repo=compile_request.github_repo,
            token=token_str,
            request_id=request_id,
        )

        logger.info(
            "fetching_repo_context_success",
            request_id=request_id,
            owner=compile_request.github_owner,
            repo=compile_request.github_repo,
            tree_count=len(repo_context.tree),
            dependencies_count=len(repo_context.dependencies),
            file_summaries_count=len(repo_context.file_summaries),
        )

    except Exception as e:
        # Log unexpected errors but don't fail the request
        # Use fallback payload to allow compilation to proceed
        logger.error(
            "fetching_repo_context_unexpected_error",
            request_id=request_id,
            owner=compile_request.github_owner,
            repo=compile_request.github_repo,
            error=str(e),
            error_type=type(e).__name__,
            using_fallback=True,
        )

        repo_context = RepoContextPayload(
            tree=create_fallback_tree(),
            dependencies=create_fallback_dependencies(),
            file_summaries=create_fallback_file_summaries(),
        )

    # Generate placeholder LLM response envelope
    # NOTE: This is intentionally created but not returned/used. It simulates
    # the future workflow where we would dispatch to LLM services. The envelope
    # is logged to validate the data structure and demonstrate the intended flow.
    # Now includes repo_context in metadata for future LLM integration.
    llm_response = create_llm_response_stub(
        request_id=request_id,
        status="pending",
        content="",
        metadata={
            "status": "stubbed",
            "details": "LLM call not yet implemented",
            "repo_context_available": True,
            "repo_context_tree_count": len(repo_context.tree),
            "repo_context_dependencies_count": len(repo_context.dependencies),
            "repo_context_file_summaries_count": len(repo_context.file_summaries),
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
