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
OpenAI Responses API client implementation.

Provides a client for the OpenAI Responses API with support for GPT-5+
models, structured output, retry logic, and proper error handling.

NOTE: This implementation targets the NEW OpenAI Responses API endpoint
(/v1/responses), which is the recommended long-term API for GPT-5+ models
as specified in LLMs.md. This is distinct from the legacy Chat Completions
API (/v1/chat/completions) and follows the latest API structure documented
at https://platform.openai.com/docs/models/gpt-5 (as of 2024-2025).

The Responses API uses a different request structure:
- Endpoint: POST /v1/responses (not /v1/chat/completions)
- Request fields: 'input' (not 'messages'), 'instructions' (not system message)
- Input format: Array with role/content objects containing 'input_text' type
- Response format: 'output' field with content array (not 'choices')

This follows the guidance from LLMs.md which explicitly states:
"Target API should be the Responses API since it is the recommended most
long term compatible option. The GPT 5 series models are supportive of the
responses API."
"""

import logging
import time
from typing import Any

import httpx

from spec_compiler.config import settings
from spec_compiler.models.llm import LlmRequestEnvelope, LlmResponseEnvelope
from spec_compiler.services.llm_client import LlmApiError, LlmClient, LlmConfigurationError
from spec_compiler.services.llm_input import LlmInputComposer

logger = logging.getLogger(__name__)

# OpenAI API configuration
# NOTE: The Responses API endpoint (/v1/responses) is the NEW recommended
# endpoint for GPT-5+ models. This is distinct from the legacy Chat Completions
# API (/v1/chat/completions). See module docstring for details.
OPENAI_API_BASE_URL = "https://api.openai.com/v1"
RESPONSES_ENDPOINT = f"{OPENAI_API_BASE_URL}/responses"

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 120.0
RETRY_STATUS_CODES = {429, 500, 502, 503, 504}  # Retry on rate limits and server errors
RETRY_BACKOFF_BASE = 2.0  # Exponential backoff base


class OpenAiResponsesClient(LlmClient):
    """
    OpenAI Responses API client.

    Implements the LlmClient interface for OpenAI's Responses API,
    targeting GPT-5+ models with structured JSON output support.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        organization_id: str | None = None,
        project_id: str | None = None,
        max_retries: int = DEFAULT_MAX_RETRIES,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        """
        Initialize the OpenAI Responses client.

        Args:
            api_key: OpenAI API key. If None, uses OPENAI_API_KEY from settings
            model: Model identifier (e.g., "gpt-5.1"). If None, uses OPENAI_MODEL from settings
            organization_id: Optional OpenAI organization ID
            project_id: Optional OpenAI project ID
            max_retries: Maximum number of retry attempts for failed requests
            timeout: Request timeout in seconds

        Raises:
            LlmConfigurationError: If API key is not configured
        """
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise LlmConfigurationError(
                "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
            )

        self.model = model or settings.openai_model
        self.organization_id = organization_id
        self.project_id = project_id
        self.max_retries = max_retries
        self.timeout = timeout

        logger.info(
            f"OpenAiResponsesClient initialized with model={self.model}, "
            f"max_retries={self.max_retries}, timeout={self.timeout}s"
        )

    def _build_headers(self) -> dict[str, str]:
        """
        Build HTTP headers for the API request.

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        if self.organization_id:
            headers["OpenAI-Organization"] = self.organization_id

        if self.project_id:
            headers["OpenAI-Project"] = self.project_id

        return headers

    def _build_request_body(self, payload: LlmRequestEnvelope) -> dict[str, Any]:
        """
        Build the request body for the Responses API.

        Args:
            payload: Request envelope with all necessary data

        Returns:
            Dictionary representing the API request body
        """
        # Compose user content using the input composer
        composer = LlmInputComposer()

        # Prepare repository context data
        tree_json = payload.repo_context.tree if payload.repo_context else []
        dependencies_json = payload.repo_context.dependencies if payload.repo_context else []
        file_summaries_json = payload.repo_context.file_summaries if payload.repo_context else []

        # Get system prompt from settings or payload
        system_prompt = payload.system_prompt.template or settings.get_system_prompt()

        # Compose the user content
        # NOTE: The system prompt is included in the user_content composition
        # AND passed separately in the 'instructions' field. This is intentional:
        # - The 'instructions' field provides high-level guidance to the model
        # - The user_content includes the system prompt as a labeled section
        #   for structured context that the model can reference
        # This dual approach ensures the system prompt is both processed by
        # the model's instruction-following mechanism and available as context.
        user_content = composer.compose_user_content(
            system_prompt=system_prompt,
            tree_json=tree_json,
            dependencies_json=dependencies_json,
            file_summaries_json=file_summaries_json,
            spec_data=payload.metadata.get("spec_data", {}),
        )

        # Build the request body according to Responses API structure
        # NOTE: This structure follows the NEW Responses API format (GPT-5+):
        # - 'input': Array of messages (not 'messages' like Chat Completions API)
        # - 'instructions': System-level guidance (not a system message in 'messages')
        # - 'content': Array with 'input_text' type objects (not plain strings)
        # - 'response_format': Structured output specification
        # See: https://platform.openai.com/docs/models/gpt-5 and module docstring
        request_body: dict[str, Any] = {
            "model": self.model,
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": user_content}],
                }
            ],
            "instructions": system_prompt,
            "response_format": {"type": "json_object"},
        }

        # Add optional parameters from system_prompt config
        if payload.system_prompt.max_tokens:
            request_body["max_output_tokens"] = payload.system_prompt.max_tokens

        return request_body

    def _make_request_with_retry(
        self, headers: dict[str, str], body: dict[str, Any], request_id: str
    ) -> dict[str, Any]:
        """
        Make API request with retry logic.

        Args:
            headers: HTTP headers
            body: Request body
            request_id: Request ID for logging

        Returns:
            Parsed JSON response

        Raises:
            LlmApiError: If request fails after all retries
        """
        last_exception: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Making OpenAI API request (attempt {attempt + 1}/{self.max_retries}) "
                    f"for request_id={request_id}"
                )

                with httpx.Client(timeout=self.timeout) as client:
                    response = client.post(
                        RESPONSES_ENDPOINT,
                        headers=headers,
                        json=body,
                    )

                    # Log request metadata without full prompt
                    logger.info(
                        f"OpenAI API response: status={response.status_code}, "
                        f"request_id={request_id}, "
                        f"model={body.get('model')}"
                    )

                    # Check for retryable status codes
                    if response.status_code in RETRY_STATUS_CODES:
                        error_msg = f"Server error {response.status_code}"
                        logger.warning(
                            f"Retryable error on attempt {attempt + 1}: {error_msg}, "
                            f"request_id={request_id}"
                        )
                        if attempt < self.max_retries - 1:
                            backoff = RETRY_BACKOFF_BASE**attempt
                            logger.info(f"Backing off {backoff}s before retry")
                            time.sleep(backoff)
                            continue
                        else:
                            raise LlmApiError(
                                f"API request failed after {self.max_retries} attempts: {error_msg}"
                            )

                    # Raise for other HTTP errors
                    response.raise_for_status()

                    # Parse and return response
                    response_data: dict[str, Any] = response.json()
                    return response_data

            except httpx.TimeoutException as e:
                last_exception = e
                logger.warning(
                    f"Timeout on attempt {attempt + 1}/{self.max_retries} "
                    f"for request_id={request_id}"
                )
                if attempt < self.max_retries - 1:
                    backoff = RETRY_BACKOFF_BASE**attempt
                    logger.info(f"Backing off {backoff}s before retry")
                    time.sleep(backoff)
                    continue

            except httpx.HTTPStatusError as e:
                last_exception = e
                logger.error(
                    f"HTTP error on attempt {attempt + 1}: status={e.response.status_code}, "
                    f"request_id={request_id}"
                )
                # Don't retry on client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    raise LlmApiError(
                        f"Client error from OpenAI API: {e.response.status_code} - "
                        f"{e.response.text[:200]}"
                    ) from e
                # Retry on server errors if attempts remain
                if attempt < self.max_retries - 1:
                    backoff = RETRY_BACKOFF_BASE**attempt
                    time.sleep(backoff)
                    continue

            except Exception as e:
                last_exception = e
                logger.error(
                    f"Unexpected error on attempt {attempt + 1} for request_id={request_id}: {e}",
                    exc_info=True,
                )
                # Do not retry on unexpected exceptions, as they likely indicate a bug.
                # Fail fast instead.
                raise LlmApiError(f"Unexpected error during API request: {e}") from e

        # All retries exhausted
        error_msg = f"API request failed after {self.max_retries} attempts"
        if last_exception:
            error_msg += f": {last_exception}"
        raise LlmApiError(error_msg) from last_exception

    def _parse_response(self, api_response: dict[str, Any], request_id: str) -> LlmResponseEnvelope:
        """
        Parse OpenAI API response into LlmResponseEnvelope.

        Args:
            api_response: Raw API response dictionary
            request_id: Request ID for correlation

        Returns:
            Parsed response envelope

        Raises:
            LlmApiError: If response cannot be parsed
        """
        try:
            # Extract output content from response
            # According to Responses API structure: output -> messages -> content
            output = api_response.get("output", [])
            if not output:
                raise LlmApiError("Response contains no output")

            # Get the first message from output
            first_message = output[0] if isinstance(output, list) else output
            content_items = first_message.get("content", [])

            if not content_items:
                raise LlmApiError("Response message contains no content")

            # Extract text from first content item
            first_content = content_items[0] if isinstance(content_items, list) else content_items
            content_text = first_content.get("text", "")

            if not content_text:
                raise LlmApiError("Response content contains no text")

            # Extract usage information
            usage_data = api_response.get("usage", {})
            usage = {
                "prompt_tokens": usage_data.get("input_tokens", 0),
                "completion_tokens": usage_data.get("output_tokens", 0),
                "total_tokens": usage_data.get("input_tokens", 0)
                + usage_data.get("output_tokens", 0),
            }

            # Build metadata
            metadata = {
                "response_id": api_response.get("id"),
                "created_at": api_response.get("created_at"),
                "status": api_response.get("status"),
            }

            # Create response envelope
            return LlmResponseEnvelope(
                request_id=request_id,
                status="success",
                content=content_text,
                model=self.model,
                usage=usage,
                metadata=metadata,
            )

        except LlmApiError:
            raise
        except Exception as e:
            logger.error(f"Failed to parse API response: {e}", exc_info=True)
            raise LlmApiError(f"Failed to parse API response: {e}") from e

    def generate_response(self, payload: LlmRequestEnvelope) -> LlmResponseEnvelope:
        """
        Generate a response from OpenAI Responses API.

        Args:
            payload: Request envelope containing all necessary data for the LLM call

        Returns:
            Response envelope with the LLM-generated content

        Raises:
            LlmConfigurationError: If the client is not properly configured
            LlmApiError: If the API call fails
        """
        logger.info(
            f"Generating OpenAI response for request_id={payload.request_id}, "
            f"model={self.model}"
        )

        try:
            # Build headers and request body
            headers = self._build_headers()
            body = self._build_request_body(payload)

            # Log request metadata (without full content)
            logger.info(
                f"Request metadata: model={body.get('model')}, "
                f"request_id={payload.request_id}, "
                f"max_output_tokens={body.get('max_output_tokens', 'default')}"
            )

            # Make request with retry logic
            api_response = self._make_request_with_retry(headers, body, payload.request_id)

            # Parse and return response
            response_envelope = self._parse_response(api_response, payload.request_id)

            logger.info(
                f"Successfully generated response for request_id={payload.request_id}, "
                f"tokens={response_envelope.usage.get('total_tokens') if response_envelope.usage else 'unknown'}"
            )

            return response_envelope

        except (LlmConfigurationError, LlmApiError):
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error generating response for request_id={payload.request_id}: {e}",
                exc_info=True,
            )
            raise LlmApiError(f"Failed to generate response: {e}") from e
