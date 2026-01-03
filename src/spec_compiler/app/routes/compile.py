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
import time
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status

from spec_compiler.config import settings
from spec_compiler.logging import get_logger
from spec_compiler.models import (
    LlmCompiledSpecOutput,
    LlmRequestEnvelope,
    RepoContextPayload,
    SystemPromptConfig,
)
from spec_compiler.models.compile import CompileRequest, CompileResponse
from spec_compiler.models.plan_status import PlanStatusMessage
from spec_compiler.services.downstream_sender import (
    DownstreamSenderError,
    DownstreamValidationError,
    get_downstream_sender,
)
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
    LlmClient,
    LlmConfigurationError,
    create_llm_client,
)
from spec_compiler.services.plan_scheduler_publisher import (
    get_publisher,
)

router = APIRouter()
logger = get_logger(__name__)


def get_provider_model_info(llm_client: LlmClient) -> tuple[str, str]:
    """
    Extract provider and model information from an LLM client instance.

    Args:
        llm_client: LLM client instance

    Returns:
        Tuple of (provider, model) strings
    """
    client_type = type(llm_client).__name__
    
    # Extract provider from client type
    if "stub" in client_type.lower():
        provider = "stub"
        model = getattr(llm_client, "model", "unknown")
    elif "openai" in client_type.lower():
        provider = "openai"
        model = getattr(llm_client, "model", settings.openai_model)
    elif "claude" in client_type.lower() or "anthropic" in client_type.lower():
        provider = "anthropic"
        model = getattr(llm_client, "model", settings.claude_model)
    else:
        provider = "unknown"
        model = "unknown"
    
    return provider, model


def publish_status_safe(
    status: str,
    plan_id: str,
    spec_index: int,
    request_id: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """
    Safely publish a plan status message, catching and logging any errors.

    This function ensures that publisher failures never prevent the main
    compile response from being returned.

    Args:
        status: Status value (in_progress, succeeded, failed)
        plan_id: Plan identifier
        spec_index: Spec index within the plan
        request_id: Request correlation ID
        error_code: Optional error code for failed status
        error_message: Optional error message for failed status
    """
    publisher = get_publisher()
    if publisher is None:
        # Publisher not configured or initialization failed
        logger.debug(
            "Skipping status publish (publisher not available)",
            status=status,
            plan_id=plan_id,
            spec_index=spec_index,
            request_id=request_id,
        )
        return

    try:
        message = PlanStatusMessage(
            plan_id=plan_id,
            spec_index=spec_index,
            status=status,  # type: ignore[arg-type]
            request_id=request_id,
            error_code=error_code,
            error_message=error_message,
        )
        publisher.publish_status(message)
        logger.info(
            "Published plan status message",
            status=status,
            plan_id=plan_id,
            spec_index=spec_index,
            request_id=request_id,
        )
    except Exception as e:
        # Log error but don't raise - publisher failures must not break compile
        logger.error(
            "Failed to publish plan status message",
            status=status,
            plan_id=plan_id,
            spec_index=spec_index,
            request_id=request_id,
            error=str(e),
            error_type=type(e).__name__,
        )


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


async def stage_validate_request(
    request: Request,
    idempotency_key: str | None,
) -> tuple[str, CompileRequest, str | None]:
    """
    Stage 1: Validate incoming compile request.

    Args:
        request: FastAPI request object
        idempotency_key: Optional idempotency key

    Returns:
        Tuple of (request_id, compile_request, safe_idempotency_key)

    Raises:
        HTTPException: On validation failure or size limit exceeded
    """
    # Get request_id from middleware
    request_id = getattr(request.state, "request_id", None)
    if not request_id:
        from spec_compiler.models import generate_request_id

        request_id = generate_request_id()

    logger.info(
        "stage_validate_request_start",
        request_id=request_id,
        stage="validate",
    )

    # Check body size limit BEFORE parsing
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
        from pydantic import ValidationError

        if isinstance(e, ValidationError):
            errors = e.errors()
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
                    try:
                        json.dumps(error["ctx"])
                        ctx_value: Any = error["ctx"]
                        serializable_error["ctx"] = ctx_value
                    except (TypeError, ValueError):
                        pass
                serializable_errors.append(serializable_error)

            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=serializable_errors,
            ) from None
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(e),
            ) from None

    # Sanitize idempotency key
    safe_idempotency_key = None
    if idempotency_key:
        sanitized = re.sub(r"[^a-zA-Z0-9\-_]", "", idempotency_key)
        safe_idempotency_key = (
            sanitized[: settings.max_idempotency_key_length] if sanitized else None
        )

    logger.info(
        "stage_validate_request_complete",
        request_id=request_id,
        stage="validate",
    )

    return request_id, compile_request, safe_idempotency_key


def stage_mint_token(
    compile_request: CompileRequest,
    request_id: str,
) -> str:
    """
    Stage 2: Mint GitHub access token.

    Args:
        compile_request: Validated compile request
        request_id: Request correlation ID

    Returns:
        GitHub access token string

    Raises:
        HTTPException: On token minting failure
    """
    logger.info(
        "stage_mint_token_start",
        request_id=request_id,
        stage="mint_token",
        owner=compile_request.github_owner,
        repo=compile_request.github_repo,
    )
    
    logger.info(
        "minting_token_start",
        request_id=request_id,
        owner=compile_request.github_owner,
        repo=compile_request.github_repo,
    )

    auth_client = GitHubAuthClient()

    try:
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
        
        logger.info(
            "stage_mint_token_complete",
            request_id=request_id,
            stage="mint_token",
            token_type=github_token.token_type,
            has_expiry=github_token.expires_at is not None,
        )

        return github_token.access_token

    except MintingError as e:
        logger.error(
            "stage_mint_token_failed",
            request_id=request_id,
            stage="mint_token",
            error=str(e),
            status_code=e.status_code,
            context=e.context,
        )

        # Publish failed status before returning error
        publish_status_safe(
            status="failed",
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            request_id=request_id,
            error_code="minting_error",
            error_message=f"Token minting service error: {str(e)[:1000]}",
        )

        # Map errors to appropriate HTTP status
        if "not configured" in str(e).lower():
            http_status = status.HTTP_500_INTERNAL_SERVER_ERROR
            error_message = "Token minting service not configured"
        elif e.status_code and e.status_code >= 500:
            http_status = status.HTTP_503_SERVICE_UNAVAILABLE
            error_message = "Token minting service temporarily unavailable"
        else:
            http_status = status.HTTP_502_BAD_GATEWAY
            error_message = "Token minting service error"

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


def stage_fetch_repo_context(
    compile_request: CompileRequest,
    token: str,
    request_id: str,
) -> RepoContextPayload:
    """
    Stage 3: Fetch repository context from GitHub.

    Args:
        compile_request: Validated compile request
        token: GitHub access token
        request_id: Request correlation ID

    Returns:
        Repository context payload with tree, dependencies, and file summaries
    """
    logger.info(
        "stage_fetch_repo_context_start",
        request_id=request_id,
        stage="fetch_repo_context",
        owner=compile_request.github_owner,
        repo=compile_request.github_repo,
    )
    
    logger.info(
        "fetching_repo_context_start",
        request_id=request_id,
        owner=compile_request.github_owner,
        repo=compile_request.github_repo,
    )

    try:
        repo_context = fetch_repo_context(
            owner=compile_request.github_owner,
            repo=compile_request.github_repo,
            token=token,
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
        
        logger.info(
            "stage_fetch_repo_context_complete",
            request_id=request_id,
            stage="fetch_repo_context",
            tree_count=len(repo_context.tree),
            dependencies_count=len(repo_context.dependencies),
            file_summaries_count=len(repo_context.file_summaries),
        )

        return repo_context

    except Exception as e:
        logger.error(
            "stage_fetch_repo_context_error",
            request_id=request_id,
            stage="fetch_repo_context",
            error=str(e),
            error_type=type(e).__name__,
            using_fallback=True,
        )

        # Use fallback data to allow compilation to proceed
        return RepoContextPayload(
            tree=create_fallback_tree(),
            dependencies=create_fallback_dependencies(),
            file_summaries=create_fallback_file_summaries(),
        )


def stage_create_llm_client(
    compile_request: CompileRequest,
    request_id: str,
) -> LlmClient:
    """
    Stage 4: Create and configure LLM client.

    Args:
        compile_request: Validated compile request
        request_id: Request correlation ID

    Returns:
        Configured LLM client instance

    Raises:
        HTTPException: On LLM configuration error
    """
    logger.info(
        "stage_create_llm_client_start",
        request_id=request_id,
        stage="create_llm_client",
        provider=settings.llm_provider,
        stub_mode=settings.llm_stub_mode,
    )

    try:
        llm_client = create_llm_client()
        
        # Extract provider/model info
        provider, model = get_provider_model_info(llm_client)
        
        logger.info(
            "llm_client_created",
            request_id=request_id,
            client_type=type(llm_client).__name__,
        )
        
        logger.info(
            "stage_create_llm_client_complete",
            request_id=request_id,
            stage="create_llm_client",
            client_type=type(llm_client).__name__,
            provider=provider,
            model=model,
        )

        return llm_client

    except LlmConfigurationError as e:
        logger.error(
            "stage_create_llm_client_failed",
            request_id=request_id,
            stage="create_llm_client",
            error=str(e),
            exc_info=True,
        )

        # Publish failed status before returning error
        publish_status_safe(
            status="failed",
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            request_id=request_id,
            error_code="llm_configuration_error",
            error_message=f"LLM service configuration error: {str(e)[:1000]}",
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


def stage_call_llm(
    llm_client: LlmClient,
    compile_request: CompileRequest,
    repo_context: RepoContextPayload,
    request_id: str,
) -> tuple[LlmCompiledSpecOutput, dict[str, Any]]:
    """
    Stage 5: Build LLM request and call LLM service with latency tracking.

    Args:
        llm_client: Configured LLM client
        compile_request: Validated compile request
        repo_context: Repository context payload
        request_id: Request correlation ID

    Returns:
        Tuple of (compiled_spec, llm_metrics) where llm_metrics contains
        latency, provider, and model information

    Raises:
        HTTPException: On LLM request build or API error
    """
    logger.info(
        "stage_call_llm_start",
        request_id=request_id,
        stage="call_llm",
    )

    # Build LLM request envelope
    try:
        system_prompt = settings.get_system_prompt()

        # Select model based on provider
        if settings.llm_provider == "openai":
            model = settings.openai_model
        elif settings.llm_provider == "anthropic":
            model = settings.claude_model
        else:
            raise ValueError(
                f"Unsupported LLM provider: {settings.llm_provider}. "
                f"Supported providers: openai, anthropic"
            )

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
        )

    except Exception as e:
        logger.error(
            "llm_request_envelope_build_failed",
            request_id=request_id,
            stage="call_llm",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

        publish_status_safe(
            status="failed",
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            request_id=request_id,
            error_code="llm_request_build_error",
            error_message=f"Failed to build LLM request: {str(e)[:1000]}",
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

    # Call LLM service with latency tracking
    provider, model_used = get_provider_model_info(llm_client)
    llm_start_time = time.time()
    
    try:
        logger.info(
            "calling_llm_service",
            request_id=request_id,
            provider=provider,
            model=model_used,
            start_timestamp=llm_start_time,
        )

        llm_response = llm_client.generate_response(llm_request)
        
        llm_end_time = time.time()
        llm_duration = llm_end_time - llm_start_time

        logger.info(
            "llm_service_response_received",
            request_id=request_id,
            provider=provider,
            model=llm_response.model or model_used,
            status=llm_response.status,
            usage_tokens=llm_response.usage.get("total_tokens", 0) if llm_response.usage else 0,
            content_length=len(llm_response.content),
            start_timestamp=llm_start_time,
            end_timestamp=llm_end_time,
            duration_seconds=llm_duration,
        )

        # Store metrics
        llm_metrics = {
            "provider": provider,
            "model": llm_response.model or model_used,
            "start_timestamp": llm_start_time,
            "end_timestamp": llm_end_time,
            "duration_seconds": llm_duration,
            "usage": llm_response.usage,
        }

    except LlmApiError as e:
        llm_end_time = time.time()
        llm_duration = llm_end_time - llm_start_time
        
        logger.error(
            "llm_service_api_error",
            request_id=request_id,
            provider=provider,
            model=model_used,
            error=str(e),
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            start_timestamp=llm_start_time,
            end_timestamp=llm_end_time,
            duration_seconds=llm_duration,
            exc_info=True,
        )

        publish_status_safe(
            status="failed",
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            request_id=request_id,
            error_code="llm_api_error",
            error_message=f"LLM service API error: {str(e)[:1000]}",
        )

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "LLM service error",
                "request_id": request_id,
                "plan_id": compile_request.plan_id,
                "spec_index": compile_request.spec_index,
                "message": "LLM service error. Please retry.",
            },
        ) from None
        
    except Exception as e:
        llm_end_time = time.time()
        llm_duration = llm_end_time - llm_start_time
        
        logger.error(
            "llm_service_unexpected_error",
            request_id=request_id,
            provider=provider,
            model=model_used,
            error=str(e),
            error_type=type(e).__name__,
            start_timestamp=llm_start_time,
            end_timestamp=llm_end_time,
            duration_seconds=llm_duration,
            exc_info=True,
        )

        publish_status_safe(
            status="failed",
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            request_id=request_id,
            error_code="llm_service_unexpected_error",
            error_message=f"Unexpected LLM service error: {str(e)[:1000]}",
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

    # Parse and validate LLM response
    try:
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
        
        # Log compiled spec sample at debug level
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
        
        logger.info(
            "stage_call_llm_complete",
            request_id=request_id,
            stage="call_llm",
            version=compiled_spec.version,
            issues_count=len(compiled_spec.issues),
            provider=provider,
            model=llm_response.model or model_used,
            duration_seconds=llm_duration,
        )

        return compiled_spec, llm_metrics

    except (ValueError, json.JSONDecodeError) as e:
        logger.error(
            "llm_response_parsing_failed",
            request_id=request_id,
            stage="call_llm",
            error=str(e),
            error_type=type(e).__name__,
            content_length=len(llm_response.content) if llm_response.content else 0,
            exc_info=True,
        )

        publish_status_safe(
            status="failed",
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            request_id=request_id,
            error_code="llm_response_parse_error",
            error_message=f"Invalid LLM response format: {str(e)[:1000]}",
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


def stage_send_downstream(
    compiled_spec: LlmCompiledSpecOutput,
    compile_request: CompileRequest,
    request_id: str,
) -> None:
    """
    Stage 6: Send compiled spec to downstream consumer.

    Args:
        compiled_spec: Parsed compiled specification
        compile_request: Original compile request
        request_id: Request correlation ID

    Raises:
        HTTPException: On downstream send error
    """
    logger.info(
        "stage_send_downstream_start",
        request_id=request_id,
        stage="send_downstream",
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
    )

    sender = get_downstream_sender()
    
    if sender is None:
        logger.warning(
            "stage_send_downstream_skipped",
            request_id=request_id,
            stage="send_downstream",
            reason="sender_not_configured",
        )
        return

    try:
        context = {
            "plan_id": compile_request.plan_id,
            "spec_index": compile_request.spec_index,
            "request_id": request_id,
            "github_owner": compile_request.github_owner,
            "github_repo": compile_request.github_repo,
        }

        sender.send_compiled_spec(compiled_spec, context)

        logger.info(
            "stage_send_downstream_complete",
            request_id=request_id,
            stage="send_downstream",
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            spec_version=compiled_spec.version,
            issues_count=len(compiled_spec.issues),
        )

    except (DownstreamSenderError, DownstreamValidationError) as e:
        logger.error(
            "stage_send_downstream_failed",
            request_id=request_id,
            stage="send_downstream",
            error=str(e),
            error_type=type(e).__name__,
        )

        publish_status_safe(
            status="failed",
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            request_id=request_id,
            error_code="downstream_sender_error",
            error_message=f"Downstream sender error: {str(e)[:1000]}",
        )

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "error": "Downstream sender error",
                "request_id": request_id,
                "plan_id": compile_request.plan_id,
                "spec_index": compile_request.spec_index,
                "message": "Failed to send compiled spec downstream. Please retry.",
            },
        ) from None

    except Exception as e:
        logger.error(
            "stage_send_downstream_unexpected_error",
            request_id=request_id,
            stage="send_downstream",
            error=str(e),
            error_type=type(e).__name__,
        )

        publish_status_safe(
            status="failed",
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            request_id=request_id,
            error_code="downstream_unexpected_error",
            error_message=f"Unexpected downstream error: {str(e)[:1000]}",
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Unexpected downstream error",
                "request_id": request_id,
                "plan_id": compile_request.plan_id,
                "spec_index": compile_request.spec_index,
                "message": "Internal error sending downstream. Please contact support.",
            },
        ) from None


def execute_compile_background(
    compile_request: CompileRequest,
    request_id: str,
) -> None:
    """
    Execute compile pipeline in background (stages 3-8).

    This function runs asynchronously after the HTTP response has been returned.
    It executes all long-running operations (token minting, LLM calls, downstream)
    and handles errors by publishing failed status.

    Args:
        compile_request: Validated compile request
        request_id: Request correlation ID
    """
    logger.info(
        "background_compile_start",
        request_id=request_id,
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
    )

    try:
        # Stage 3: Mint GitHub token
        token_str = stage_mint_token(compile_request, request_id)

        # Stage 4: Fetch repository context
        repo_context = stage_fetch_repo_context(compile_request, token_str, request_id)

        # Stage 5: Create LLM client
        llm_client = stage_create_llm_client(compile_request, request_id)

        # Stage 6: Call LLM service with latency tracking
        compiled_spec, llm_metrics = stage_call_llm(
            llm_client, compile_request, repo_context, request_id
        )

        # Stage 7: Send downstream
        stage_send_downstream(compiled_spec, compile_request, request_id)

        # Stage 8: Publish succeeded status
        logger.info(
            "stage_publish_succeeded",
            request_id=request_id,
            stage="publish_succeeded",
        )
        
        publish_status_safe(
            status="succeeded",
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            request_id=request_id,
        )

        logger.info(
            "background_compile_complete",
            request_id=request_id,
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            compiled_version=compiled_spec.version,
            compiled_issues_count=len(compiled_spec.issues),
            llm_provider=llm_metrics["provider"],
            llm_model=llm_metrics["model"],
            llm_duration_seconds=llm_metrics["duration_seconds"],
        )

    except HTTPException as e:
        # HTTPException from stages already published failed status
        # Just log the error
        logger.error(
            "background_compile_failed_http",
            request_id=request_id,
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            status_code=e.status_code,
            detail=e.detail,
        )

    except Exception as e:
        # Unexpected error - publish failed status
        logger.error(
            "background_compile_failed_unexpected",
            request_id=request_id,
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )

        publish_status_safe(
            status="failed",
            plan_id=compile_request.plan_id,
            spec_index=compile_request.spec_index,
            request_id=request_id,
            error_code="background_unexpected_error",
            error_message=f"Unexpected background processing error: {str(e)[:1000]}",
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
    background_tasks: BackgroundTasks,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> CompileResponse:
    """
    Compile a specification with LLM integration (async 202 workflow).

    Executes a staged pipeline for processing specifications:
    1. Validate request and check size limits
    2. Publish in-progress status
    3. Enqueue background task for async processing
    4. Return HTTP 202 Accepted immediately

    Background task executes:
    3. Mint GitHub access token
    4. Fetch repository context
    5. Create LLM client
    6. Call LLM with latency tracking
    7. Send compiled spec downstream
    8. Publish succeeded status

    Args:
        request: FastAPI request object (for accessing request_id and body)
        background_tasks: FastAPI background tasks manager
        idempotency_key: Optional idempotency key for client-side deduplication

    Returns:
        CompileResponse with request tracking information

    Raises:
        HTTPException: Various status codes based on validation failure
    """
    # Stage 1: Validate request
    request_id, compile_request, safe_idempotency_key = await stage_validate_request(request, idempotency_key)

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

    # Stage 2: Publish in_progress status
    logger.info(
        "stage_publish_in_progress",
        request_id=request_id,
        stage="publish_in_progress",
    )
    
    publish_status_safe(
        status="in_progress",
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
        request_id=request_id,
    )

    # Stage 3: Enqueue background task for async processing
    logger.info(
        "enqueuing_background_task",
        request_id=request_id,
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
    )
    
    background_tasks.add_task(
        execute_compile_background,
        compile_request=compile_request,
        request_id=request_id,
    )

    # Stage 4: Return HTTP 202 Accepted immediately
    response = CompileResponse(
        request_id=request_id,
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
        status="accepted",
        message="Request accepted for processing",
    )

    logger.info(
        "Compile request accepted for async processing",
        request_id=request_id,
        plan_id=compile_request.plan_id,
        spec_index=compile_request.spec_index,
    )

    return response
