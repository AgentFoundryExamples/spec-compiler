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
OpenAI Responses API client implementation using official SDK.

Provides a client for the OpenAI Responses API with support for GPT-5+
models, structured output, retry logic, and proper error handling.

This implementation uses the official OpenAI Python SDK (openai package v2.14+)
which provides native support for the Responses API (`client.responses.create()`).

The Responses API is the recommended long-term API for GPT-5+ models as specified
in LLMs.md. It uses a different structure than the legacy Chat Completions API:
- Request fields: 'input' (user message), 'instructions' (system prompt)
- Supports structured outputs via 'text' parameter with JSON schema or format string
- Response format: Response object with 'output' field

This follows the guidance from LLMs.md which explicitly states:
"Target API should be the Responses API since it is the recommended most
long term compatible option. The GPT 5 series models are supportive of the
responses API."
"""

import logging
import time

from openai import APIError, APITimeoutError, OpenAI, RateLimitError
from openai.types.responses.response import Response

from spec_compiler.config import settings
from spec_compiler.models.llm import LlmRequestEnvelope, LlmResponseEnvelope
from spec_compiler.services.llm_client import LlmApiError, LlmClient, LlmConfigurationError
from spec_compiler.services.llm_input import LlmInputComposer, LlmInputStructure

logger = logging.getLogger(__name__)

# Retry configuration
RETRY_BACKOFF_BASE = 2.0  # Exponential backoff base


class OpenAiResponsesClient(LlmClient):
    """
    OpenAI Responses API client using official SDK.

    Implements the LlmClient interface for OpenAI's Responses API,
    targeting GPT-5+ models with structured JSON output support using
    the official OpenAI Python SDK.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        organization_id: str | None = None,
        project_id: str | None = None,
        base_url: str | None = None,
        max_retries: int | None = None,
        timeout: float | None = None,
    ):
        """
        Initialize the OpenAI Responses client.

        Args:
            api_key: OpenAI API key. If None, uses OPENAI_API_KEY from settings
            model: Model identifier (e.g., "gpt-5.1"). If None, uses OPENAI_MODEL from settings
            organization_id: Optional OpenAI organization ID. If None, uses OPENAI_ORGANIZATION from settings
            project_id: Optional OpenAI project ID. If None, uses OPENAI_PROJECT from settings
            base_url: Optional base URL for API. If None, uses OPENAI_API_BASE from settings
            max_retries: Maximum number of retry attempts. If None, uses LLM_MAX_RETRIES from settings
            timeout: Request timeout in seconds. If None, uses LLM_TIMEOUT from settings

        Raises:
            LlmConfigurationError: If API key is not configured
        """
        self.api_key = api_key or settings.openai_api_key
        if not self.api_key:
            raise LlmConfigurationError(
                "OpenAI API key not configured. Set OPENAI_API_KEY environment variable."
            )

        self.model = model or settings.openai_model
        self.organization_id = organization_id or settings.openai_organization
        self.project_id = project_id or settings.openai_project
        self.base_url = base_url or settings.openai_api_base
        self.max_retries = max_retries if max_retries is not None else settings.llm_max_retries
        self.timeout = timeout if timeout is not None else settings.llm_timeout

        # Initialize OpenAI client with custom configuration
        client_kwargs = {
            "api_key": self.api_key,
            "timeout": self.timeout,
            "max_retries": 0,  # We handle retries ourselves for better control
        }

        if self.organization_id:
            client_kwargs["organization"] = self.organization_id
        if self.project_id:
            client_kwargs["project"] = self.project_id
        if self.base_url:
            client_kwargs["base_url"] = self.base_url

        self.client = OpenAI(**client_kwargs)

        logger.info(
            f"OpenAiResponsesClient initialized with model={self.model}, "
            f"max_retries={self.max_retries}, timeout={self.timeout}s"
        )

    def _compose_input_structure(self, payload: LlmRequestEnvelope) -> LlmInputStructure:
        """
        Compose the input structure for the Responses API.

        Returns separated system prompt and user content, where the system prompt
        will be passed via the 'instructions' parameter and user content via 'input'.

        Args:
            payload: Request envelope with all necessary data

        Returns:
            LlmInputStructure with separated system_prompt and user_content
        """
        composer = LlmInputComposer()

        # Prepare repository context data
        tree_json = payload.repo_context.tree if payload.repo_context else []
        dependencies_json = payload.repo_context.dependencies if payload.repo_context else []
        file_summaries_json = payload.repo_context.file_summaries if payload.repo_context else []

        # Get system prompt from settings or payload
        system_prompt = payload.system_prompt.template or settings.get_system_prompt()

        # Compose with separated structure (NEW approach)
        return composer.compose_separated(
            system_prompt=system_prompt,
            tree_json=tree_json,
            dependencies_json=dependencies_json,
            file_summaries_json=file_summaries_json,
            spec_data=payload.metadata.get("spec_data", {}),
        )

    def _make_request_with_retry(
        self, instructions: str, input_content: str, max_tokens: int, request_id: str
    ) -> Response:
        """
        Make API request with retry logic using the official SDK.

        Args:
            instructions: System instructions (system prompt)
            input_content: User input content
            max_tokens: Maximum tokens for response
            request_id: Request ID for logging

        Returns:
            Response object from SDK

        Raises:
            LlmApiError: If request fails after all retries
        """
        last_exception: Exception | None = None
        start_time = time.time()

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Making OpenAI Responses API request (attempt {attempt + 1}/{self.max_retries}) "
                    f"for request_id={request_id}"
                )

                # Make the API call using Responses API
                # The Responses API uses 'instructions' for system context
                # and 'input' for the user message
                # Note: text="json" enforces JSON output
                response = self.client.responses.create(
                    model=self.model,
                    instructions=instructions,
                    input=input_content,
                    max_output_tokens=max_tokens,
                    text="json",  # Enforce JSON output format
                )

                # Log successful request with latency
                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"OpenAI Responses API response: status=success, "
                    f"request_id={request_id}, "
                    f"model={self.model}, "
                    f"latency_ms={latency_ms:.2f}"
                )

                return response

            except RateLimitError as e:
                last_exception = e
                logger.warning(
                    f"Rate limit error on attempt {attempt + 1}: {str(e)}, "
                    f"request_id={request_id}"
                )
                if attempt < self.max_retries - 1:
                    backoff = RETRY_BACKOFF_BASE**attempt
                    logger.info(f"Backing off {backoff}s before retry")
                    time.sleep(backoff)
                    continue

            except APITimeoutError as e:
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

            except APIError as e:
                last_exception = e
                # Check if it's a retryable server error (5xx)
                status_code = getattr(e, "status_code", None)
                logger.error(
                    f"API error on attempt {attempt + 1}: status={status_code}, "
                    f"request_id={request_id}, error={str(e)}"
                )

                # Don't retry on client errors (4xx)
                if status_code and 400 <= status_code < 500:
                    raise LlmApiError(
                        f"Client error from OpenAI Responses API: {status_code} - {str(e)}"
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
                # Do not retry on unexpected exceptions
                raise LlmApiError(f"Unexpected error during API request: {e}") from e

        # All retries exhausted
        latency_ms = (time.time() - start_time) * 1000
        error_msg = (
            f"API request failed after {self.max_retries} attempts (latency: {latency_ms:.2f}ms)"
        )
        if last_exception:
            error_msg += f": {last_exception}"
        logger.error(
            f"All retries exhausted for request_id={request_id}, "
            f"latency_ms={latency_ms:.2f}, error={error_msg}"
        )
        raise LlmApiError(error_msg) from last_exception

    def _parse_response(self, api_response: Response, request_id: str) -> LlmResponseEnvelope:
        """
        Parse OpenAI Responses API response into LlmResponseEnvelope.

        Args:
            api_response: Response object from SDK
            request_id: Request ID for correlation

        Returns:
            Parsed response envelope

        Raises:
            LlmApiError: If response cannot be parsed
        """
        try:
            # Extract output from response
            # Response API returns output as a list of output items
            if not api_response.output or len(api_response.output) == 0:
                raise LlmApiError("Response contains no output")

            # Get the first output item
            first_output = api_response.output[0]

            # Extract text content
            content_text = getattr(first_output, "text", None) or getattr(
                first_output, "content", ""
            )
            if not content_text:
                raise LlmApiError("Response output contains no text content")

            # Extract usage information
            usage = {}
            if api_response.usage:
                usage = {
                    "prompt_tokens": getattr(api_response.usage, "input_tokens", 0),
                    "completion_tokens": getattr(api_response.usage, "output_tokens", 0),
                    "total_tokens": getattr(api_response.usage, "total_tokens", 0),
                }

            # Build metadata
            metadata = {
                "response_id": api_response.id,
                "created": getattr(api_response, "created", None)
                or getattr(api_response, "created_at", None),
                "model": api_response.model or self.model,
                "provider": "openai",
            }

            # Create response envelope
            return LlmResponseEnvelope(
                request_id=request_id,
                status="success",
                content=content_text,
                model=api_response.model or self.model,
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
        start_time = time.time()

        logger.info(
            f"Generating OpenAI response for request_id={payload.request_id}, "
            f"model={self.model}, provider=openai"
        )

        try:
            # Compose input with separated system prompt and user content
            input_structure = self._compose_input_structure(payload)

            # Get max tokens
            max_tokens = payload.system_prompt.max_tokens or 15000

            # Log request metadata (without full content)
            logger.info(
                f"Request metadata: model={self.model}, "
                f"request_id={payload.request_id}, "
                f"max_output_tokens={max_tokens}, "
                f"provider=openai"
            )

            # Make request with retry logic
            # Pass system_prompt via 'instructions' and user_content via 'input'
            api_response = self._make_request_with_retry(
                input_structure.system_prompt,  # System prompt goes to instructions
                input_structure.user_content,  # User content goes to input
                max_tokens,
                payload.request_id,
            )

            # Parse and return response
            response_envelope = self._parse_response(api_response, payload.request_id)

            # Calculate and log latency
            latency_ms = (time.time() - start_time) * 1000
            logger.info(
                f"Successfully generated response for request_id={payload.request_id}, "
                f"tokens={response_envelope.usage.get('total_tokens') if response_envelope.usage else 'unknown'}, "
                f"latency_ms={latency_ms:.2f}, "
                f"provider=openai, "
                f"model={self.model}"
            )

            # Add latency to metadata
            if response_envelope.metadata:
                response_envelope.metadata["latency_ms"] = latency_ms

            return response_envelope

        except (LlmConfigurationError, LlmApiError):
            raise
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            logger.error(
                f"Unexpected error generating response for request_id={payload.request_id}: {e}, "
                f"latency_ms={latency_ms:.2f}",
                exc_info=True,
            )
            raise LlmApiError(f"Failed to generate response: {e}") from e
