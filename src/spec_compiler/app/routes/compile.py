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
from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Request, status

from spec_compiler.config import settings
from spec_compiler.logging import get_logger
from spec_compiler.models import (
    LlmCompiledSpecOutput,
    LlmRequestEnvelope,
    RepoContextPayload,
    SystemPromptConfig,
)
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
from spec_compiler.services.llm_client import (
    LlmApiError,
    LlmConfigurationError,
    create_llm_client,
)

router = APIRouter()
logger = get_logger(__name__)


def _fetch_and_log_context_file(
    repo_client: GitHubRepoClient,
    owner: str,
    repo: str,
    file_path: str,
    token: str,
    request_id: str,
    data_key: str,
    fallback_factory: Any,
    success_log_event: str,
    error_log_event: str,
    invalid_json_log_event: str,
) -> dict[str, Any]:
    """
    Helper to fetch a single repo context file with logging and fallback.

    Args:
        repo_client: GitHubRepoClient instance
        owner: GitHub repository owner
        repo: GitHub repository name
        file_path: Path to the file in the repository
        token: GitHub access token
        request_id: Request ID for logging
        data_key: Key in the response dict containing the data list
        fallback_factory: Callable that returns fallback data
        success_log_event: Log event name for success
        error_log_event: Log event name for GitHub file errors
        invalid_json_log_event: Log event name for invalid JSON errors

    Returns:
        Dictionary with data_key mapped to the fetched or fallback data
    """
    try:
        data = repo_client.get_json_file(owner=owner, repo=repo, path=file_path, token=token)
        count = len(data.get(data_key, [])) if isinstance(data, dict) else 0
        logger.info(
            success_log_event,
            request_id=request_id,
            owner=owner,
            repo=repo,
            count=count,
        )
        return data
    except GitHubFileError as e:
        logger.warning(
            error_log_event,
            request_id=request_id,
            owner=owner,
            repo=repo,
            error=str(e),
            status_code=e.status_code,
            using_fallback=True,
        )
    except InvalidJSONError as e:
        logger.warning(
            invalid_json_log_event,
            request_id=request_id,
            owner=owner,
            repo=repo,
            error=str(e),
            using_fallback=True,
        )
    return {data_key: fallback_factory()}


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

    # Fetch tree.json
    tree_data = _fetch_and_log_context_file(
        repo_client,
        owner,
        repo,
        f"{base_path}/tree.json",
        token,
        request_id,
        "tree",
        create_fallback_tree,
        "repo_context_tree_success",
        "repo_context_tree_error",
        "repo_context_tree_invalid_json",
    )

    # Fetch dependencies.json
    dependencies_data = _fetch_and_log_context_file(
        repo_client,
        owner,
        repo,
        f"{base_path}/dependencies.json",
        token,
        request_id,
        "dependencies",
        create_fallback_dependencies,
        "repo_context_dependencies_success",
        "repo_context_dependencies_error",
        "repo_context_dependencies_invalid_json",
    )

    # Fetch file-summaries.json
    file_summaries_data = _fetch_and_log_context_file(
        repo_client,
        owner,
        repo,
        f"{base_path}/file-summaries.json",
        token,
        request_id,
        "summaries",
        create_fallback_file_summaries,
        "repo_context_file_summaries_success",
        "repo_context_file_summaries_error",
        "repo_context_file_summaries_invalid_json",
    )

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

    Accepts a compile request, validates the payload, fetches repository context,
    invokes the configured LLM provider (or stub) to generate a compiled spec,
    parses and validates the result, and returns a 202 Accepted response.

    The workflow includes:
    1. Minting GitHub token for repository access
    2. Fetching repository analysis files (tree.json, dependencies.json, file-summaries.json)
    3. Creating LLM client based on configuration (stub or real provider)
    4. Building LLM request envelope with system prompt, repo context, and spec data
    5. Calling LLM service to generate compiled specification
    6. Parsing and validating the LLM response as LlmCompiledSpecOutput
    7. Logging the compiled spec and returning success response

    Args:
        request: FastAPI request object (for accessing request_id and body)
        idempotency_key: Optional idempotency key for client-side deduplication

    Returns:
        CompileResponse with request tracking information

    Raises:
        HTTPException: 413 if request body exceeds size limit
        HTTPException: 422 if validation fails (handled by Pydantic)
        HTTPException: 500 if LLM configuration error or internal error
        HTTPException: 502 if token minting service error (4xx)
        HTTPException: 503 if token minting service error (5xx) or LLM API error
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
                serializable_error: dict[str, Any] = {
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
                        ctx_value: Any = error["ctx"]
                        serializable_error["ctx"] = ctx_value
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
        if "not configured" in str(e).lower():
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_message = "Token minting service not configured"
        elif e.status_code and e.status_code >= 500:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            error_message = "Token minting service temporarily unavailable"
        else:
            # Catches 4xx errors from minting service and other connection issues
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
        ) from None

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

    # Create LLM client based on configuration (stub or real provider)
    try:
        logger.info(
            "creating_llm_client",
            request_id=request_id,
            provider=settings.llm_provider,
            stub_mode=settings.llm_stub_mode,
        )
        llm_client = create_llm_client()
        logger.info(
            "llm_client_created",
            request_id=request_id,
            client_type=type(llm_client).__name__,
        )
    except LlmConfigurationError as e:
        logger.error(
            "llm_client_configuration_failed",
            request_id=request_id,
            error=str(e),
            exc_info=True,  # Log full traceback for debugging
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "LLM service not configured",
                "request_id": request_id,
                "plan_id": compile_request.plan_id,
                "spec_index": compile_request.spec_index,
                "message": "LLM service configuration error. Please contact support.",
            },
        ) from None

    # Build LLM request envelope with repo context and spec data
    try:
        logger.info(
            "building_llm_request_envelope",
            request_id=request_id,
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
        )

        # Get system prompt from configuration
        system_prompt = settings.get_system_prompt()

        # Select model based on provider with explicit error handling
        if settings.llm_provider == "openai":
            model = settings.openai_model
        elif settings.llm_provider == "anthropic":
            model = settings.claude_model
        else:
            raise ValueError(
                f"Unsupported LLM provider: {settings.llm_provider}. "
                f"Supported providers: openai, anthropic"
            )

        # Create request envelope
        llm_request = LlmRequestEnvelope(
            request_id=request_id,
            model=model,
            system_prompt=SystemPromptConfig(
                template=system_prompt,
                max_tokens=4096,
            ),
            repo_context=repo_context,
            metadata={
                "plan_id": compile_request.plan_id,
                "spec_index": compile_request.spec_index,
                "github_owner": compile_request.github_owner,
                "github_repo": compile_request.github_repo,
                "spec_data": compile_request.spec_data,
            },
        )

        logger.info(
            "llm_request_envelope_built",
            request_id=request_id,
            model=llm_request.model,
            repo_context_tree_count=len(repo_context.tree),
            repo_context_dependencies_count=len(repo_context.dependencies),
            repo_context_file_summaries_count=len(repo_context.file_summaries),
        )

    except Exception as e:
        logger.error(
            "llm_request_envelope_build_failed",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,  # Log full traceback for debugging
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Failed to build LLM request",
                "request_id": request_id,
                "plan_id": compile_request.plan_id,
                "spec_index": compile_request.spec_index,
                "message": "Internal error building request. Please retry or contact support.",
            },
        ) from None

    # Call LLM service to generate compiled spec
    try:
        logger.info(
            "calling_llm_service",
            request_id=request_id,
            provider=settings.llm_provider,
            model=llm_request.model,
        )

        llm_response = llm_client.generate_response(llm_request)

        logger.info(
            "llm_service_response_received",
            request_id=request_id,
            status=llm_response.status,
            model=llm_response.model,
            usage_tokens=llm_response.usage.get("total_tokens", 0) if llm_response.usage else 0,
            content_length=len(llm_response.content),
        )

    except LlmApiError as e:
        logger.error(
            "llm_service_api_error",
            request_id=request_id,
            error=str(e),
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            exc_info=True,  # Log full traceback for debugging
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "LLM service error",
                "request_id": request_id,
                "plan_id": compile_request.plan_id,
                "spec_index": compile_request.spec_index,
                "message": "LLM service temporarily unavailable. Please retry.",
            },
        ) from None
    except Exception as e:
        logger.error(
            "llm_service_unexpected_error",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,  # Log full traceback for debugging
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Unexpected LLM service error",
                "request_id": request_id,
                "plan_id": compile_request.plan_id,
                "spec_index": compile_request.spec_index,
                "message": "Internal error calling LLM service. Please contact support.",
            },
        ) from None

    # Parse and validate LLM response as compiled spec output
    try:
        # Check for empty response content
        if not llm_response.content:
            logger.error(
                "llm_response_empty",
                request_id=request_id,
                plan_id=compile_request.plan_id,
                spec_index=compile_request.spec_index,
            )
            raise ValueError("LLM response content is empty")

        logger.info(
            "parsing_llm_response",
            request_id=request_id,
            content_length=len(llm_response.content),
        )

        compiled_spec = LlmCompiledSpecOutput.from_json_string(llm_response.content)

        logger.info(
            "llm_response_parsed_successfully",
            request_id=request_id,
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            version=compiled_spec.version,
            issues_count=len(compiled_spec.issues),
        )

        # Log compiled spec at debug level (first issue only for brevity)
        if compiled_spec.issues:
            first_issue = compiled_spec.issues[0]
            logger.debug(
                "compiled_spec_sample",
                request_id=request_id,
                version=compiled_spec.version,
                first_issue_id=first_issue.get("id", "unknown"),
                first_issue_title=first_issue.get("title", "")[:100],
                total_issues=len(compiled_spec.issues),
            )

    except (ValueError, json.JSONDecodeError) as e:
        logger.error(
            "llm_response_parsing_failed",
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
            content_length=len(llm_response.content) if llm_response.content else 0,
            exc_info=True,  # Log full traceback for debugging
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Invalid LLM response format",
                "request_id": request_id,
                "plan_id": compile_request.plan_id,
                "spec_index": compile_request.spec_index,
                "message": "LLM returned invalid response format. Please retry or contact support.",
            },
        ) from None

    # Create and return success response
    response = CompileResponse(
        request_id=request_id,
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
        status="accepted",
        message="Request accepted for processing",
    )

    logger.info(
        "Compile request completed successfully",
        request_id=request_id,
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
        compiled_version=compiled_spec.version,
        compiled_issues_count=len(compiled_spec.issues),
    )

    return response
