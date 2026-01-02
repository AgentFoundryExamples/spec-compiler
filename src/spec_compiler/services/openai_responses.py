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
OpenAI Chat Completions API client implementation.

Provides a client for the OpenAI Chat Completions API with support for GPT-5+
models, structured JSON output, retry logic, and proper error handling.

This implementation uses the official OpenAI Python SDK (openai package) and
targets GPT-5.1 models as specified in LLMs.md. The Chat Completions API is
the standard, long-term supported API for GPT models.

API Structure:
- Uses client.chat.completions.create() from official SDK
- Messages format: Array of {'role': 'system'|'user', 'content': str}
- Structured output: response_format={'type': 'json_object'}
- Response format: Standard ChatCompletion object with 'choices' array

This follows the guidance from LLMs.md which specifies GPT-5.1 as the target
model using the official openai SDK.
"""

import logging
import time
from typing import Any

from openai import OpenAI, APIError, APITimeoutError, RateLimitError
from openai.types.chat import ChatCompletion

from spec_compiler.config import settings
from spec_compiler.models.llm import LlmRequestEnvelope, LlmResponseEnvelope
from spec_compiler.services.llm_client import LlmApiError, LlmClient, LlmConfigurationError
from spec_compiler.services.llm_input import LlmInputComposer

logger = logging.getLogger(__name__)

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 120.0
RETRY_BACKOFF_BASE = 2.0  # Exponential backoff base


class OpenAiResponsesClient(LlmClient):
    """
    OpenAI Chat Completions API client.

    Implements the LlmClient interface for OpenAI's Chat Completions API,
    targeting GPT-5+ models with structured JSON output support using the
    official OpenAI Python SDK.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        organization: str | None = None,
        project: str | None = None,
        base_url: str | None = None,
        max_retries: int | None = None,
        timeout: float | None = None,
    ):
        """
        Initialize the OpenAI client.

        Args:
            api_key: OpenAI API key. If None, uses OPENAI_API_KEY from settings
            model: Model identifier (e.g., "gpt-5.1"). If None, uses OPENAI_MODEL from settings
            organization: Optional OpenAI organization ID. If None, uses OPENAI_ORGANIZATION from settings
            project: Optional OpenAI project ID. If None, uses OPENAI_PROJECT from settings
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
        self.organization = organization or settings.openai_organization
        self.project = project or settings.openai_project
        self.base_url = base_url or settings.openai_api_base
        self.max_retries = max_retries if max_retries is not None else settings.llm_max_retries
        self.timeout = timeout if timeout is not None else settings.llm_timeout

        # Initialize OpenAI client with custom configuration
        # Note: SDK handles retries internally when max_retries > 0
        self.client = OpenAI(
            api_key=self.api_key,
            organization=self.organization,
            project=self.project,
            base_url=self.base_url,
            max_retries=0,  # We handle retries ourselves for better control
            timeout=self.timeout,
        )

        logger.info(
            f"OpenAiResponsesClient initialized with model={self.model}, "
            f"max_retries={self.max_retries}, timeout={self.timeout}s"
        )

    def _build_request_params(self, payload: LlmRequestEnvelope) -> dict[str, Any]:
        """
        Build the request parameters for the Chat Completions API.

        Args:
            payload: Request envelope with all necessary data

        Returns:
            Dictionary representing the API request parameters
        """
        # Compose user content using the input composer
        composer = LlmInputComposer()

        # Prepare repository context data
        tree_json = payload.repo_context.tree if payload.repo_context else []
        dependencies_json = payload.repo_context.dependencies if payload.repo_context else []
        file_summaries_json = payload.repo_context.file_summaries if payload.repo_context else []

        # Get system prompt from settings or payload
        system_prompt = payload.system_prompt.template or settings.get_system_prompt()

        # Compose the user content (includes system prompt and repo context)
        user_content = composer.compose_user_content(
            system_prompt=system_prompt,
            tree_json=tree_json,
            dependencies_json=dependencies_json,
            file_summaries_json=file_summaries_json,
            spec_data=payload.metadata.get("spec_data", {}),
        )

        # Build the request parameters according to Chat Completions API structure
        # Uses standard messages format: [{"role": "system", "content": ...}, {"role": "user", "content": ...}]
        request_params: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        }

        # Add optional parameters from system_prompt config
        if payload.system_prompt.max_tokens:
            request_params["max_tokens"] = payload.system_prompt.max_tokens

        return request_params

    def _make_request_with_retry(
        self, request_params: dict[str, Any], request_id: str
    ) -> ChatCompletion:
        """
        Make API request with retry logic using the official SDK.

        Args:
            request_params: Request parameters for the API
            request_id: Request ID for logging

        Returns:
            ChatCompletion response object from SDK

        Raises:
            LlmApiError: If request fails after all retries
        """
        last_exception: Exception | None = None
        start_time = time.time()

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Making OpenAI API request (attempt {attempt + 1}/{self.max_retries}) "
                    f"for request_id={request_id}"
                )

                # Make the API call using official SDK
                response = self.client.chat.completions.create(**request_params)

                # Log successful request with latency
                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"OpenAI API response: status=success, "
                    f"request_id={request_id}, "
                    f"model={request_params.get('model')}, "
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
                        f"Client error from OpenAI API: {status_code} - {str(e)}"
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

    def _parse_response(self, api_response: ChatCompletion, request_id: str) -> LlmResponseEnvelope:
        """
        Parse OpenAI API response into LlmResponseEnvelope.

        Args:
            api_response: ChatCompletion response object from SDK
            request_id: Request ID for correlation

        Returns:
            Parsed response envelope

        Raises:
            LlmApiError: If response cannot be parsed
        """
        try:
            # Extract content from response
            # Chat Completions API returns: choices[0].message.content
            if not api_response.choices:
                raise LlmApiError("Response contains no choices")

            first_choice = api_response.choices[0]
            if not first_choice.message or not first_choice.message.content:
                raise LlmApiError("Response choice contains no message content")

            content_text = first_choice.message.content

            # Extract usage information
            usage = {
                "prompt_tokens": api_response.usage.prompt_tokens if api_response.usage else 0,
                "completion_tokens": (
                    api_response.usage.completion_tokens if api_response.usage else 0
                ),
                "total_tokens": api_response.usage.total_tokens if api_response.usage else 0,
            }

            # Build metadata
            metadata = {
                "response_id": api_response.id,
                "created": api_response.created,
                "model": api_response.model,
                "finish_reason": first_choice.finish_reason,
                "provider": "openai",
            }

            # Create response envelope
            return LlmResponseEnvelope(
                request_id=request_id,
                status="success",
                content=content_text,
                model=api_response.model,
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
        Generate a response from OpenAI Chat Completions API.

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
            # Build request parameters
            request_params = self._build_request_params(payload)

            # Log request metadata (without full content)
            logger.info(
                f"Request metadata: model={request_params.get('model')}, "
                f"request_id={payload.request_id}, "
                f"max_tokens={request_params.get('max_tokens', 'default')}, "
                f"provider=openai"
            )

            # Make request with retry logic
            api_response = self._make_request_with_retry(request_params, payload.request_id)

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
