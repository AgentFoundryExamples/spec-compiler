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
Anthropic Claude Messages API client implementation.

Provides a client for the Anthropic Messages API with support for Claude Sonnet 4.5+
models, JSON output, retry logic, and proper error handling.

This implementation targets the Messages API (API version 2023-06-01 or newer) as
specified in LLMs.md, which is the recommended long-term API for Claude Sonnet/Opus 4+ models.
"""

import logging
import time
from typing import Any

from anthropic import Anthropic, APIError, APITimeoutError, RateLimitError
from anthropic.types import Message

from spec_compiler.config import settings
from spec_compiler.models.llm import LlmRequestEnvelope, LlmResponseEnvelope
from spec_compiler.services.llm_client import LlmApiError, LlmClient, LlmConfigurationError
from spec_compiler.services.llm_input import LlmInputComposer

logger = logging.getLogger(__name__)

# Retry configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_TIMEOUT_SECONDS = 120.0
RETRY_BACKOFF_BASE = 2.0


class ClaudeLlmClient(LlmClient):
    """
    Anthropic Claude Messages API client.

    Implements the LlmClient interface for Anthropic's Messages API,
    targeting Claude Sonnet 4.5+ models with JSON output support.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        max_retries: int | None = None,
        timeout: float | None = None,
    ):
        """
        Initialize the Anthropic Claude client.

        Args:
            api_key: Anthropic API key. If None, uses CLAUDE_API_KEY from settings
            model: Model identifier (e.g., "claude-3-5-sonnet-20241022"). If None, uses CLAUDE_MODEL from settings
            base_url: Optional base URL for API (defaults to Anthropic's default)
            max_retries: Maximum number of retry attempts. If None, uses LLM_MAX_RETRIES from settings
            timeout: Request timeout in seconds. If None, uses LLM_TIMEOUT from settings

        Raises:
            LlmConfigurationError: If API key is not configured
        """
        self.api_key = api_key or settings.claude_api_key
        if not self.api_key:
            raise LlmConfigurationError(
                "Anthropic API key not configured. Set CLAUDE_API_KEY environment variable."
            )

        self.model = model or settings.claude_model
        self.base_url = base_url or settings.claude_api_base
        self.max_retries = max_retries if max_retries is not None else settings.llm_max_retries
        self.timeout = timeout if timeout is not None else settings.llm_timeout

        # Initialize Anthropic client with custom configuration
        self.client = Anthropic(
            api_key=self.api_key,
            base_url=self.base_url,
            max_retries=0,  # We handle retries ourselves for better control
            timeout=self.timeout,
        )

        logger.info(
            f"ClaudeLlmClient initialized with model={self.model}, "
            f"max_retries={self.max_retries}, timeout={self.timeout}s"
        )

    def _build_request_payload(self, payload: LlmRequestEnvelope) -> dict[str, Any]:
        """
        Build the request payload for the Anthropic Messages API.

        Args:
            payload: Request envelope with all necessary data

        Returns:
            Dictionary representing the API request parameters

        Raises:
            LlmConfigurationError: If composed structure has empty fields
        """
        # Use the new separated composition approach
        composer = LlmInputComposer()

        # Prepare repository context data
        tree_json = payload.repo_context.tree if payload.repo_context else []
        dependencies_json = payload.repo_context.dependencies if payload.repo_context else []
        file_summaries_json = payload.repo_context.file_summaries if payload.repo_context else []

        # Get system prompt from settings or payload
        system_prompt = payload.system_prompt.template or settings.get_system_prompt()

        # Compose with separated structure (NEW approach)
        input_structure = composer.compose_separated(
            system_prompt=system_prompt,
            tree_json=tree_json,
            dependencies_json=dependencies_json,
            file_summaries_json=file_summaries_json,
            spec_data=payload.metadata.get("spec_data", {}),
        )

        # Validate that composed structure has non-empty fields
        if not input_structure.system_prompt or not input_structure.system_prompt.strip():
            raise LlmConfigurationError(
                "Composed input structure has empty system prompt. "
                "Check system prompt configuration."
            )
        if not input_structure.user_content or not input_structure.user_content.strip():
            raise LlmConfigurationError(
                "Composed input structure has empty user content. "
                "Check repository context and spec data."
            )

        # Build the request payload according to Anthropic Messages API structure
        # Messages API uses:
        # - 'model': Model identifier
        # - 'messages': Array of message objects with role and content
        # - 'system': System prompt (separate from messages)
        # - 'max_tokens': Maximum tokens to generate (required)
        request_params: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": input_structure.user_content,  # User content without system prompt
                }
            ],
            "system": input_structure.system_prompt,  # System prompt passed separately
            "max_tokens": payload.system_prompt.max_tokens or 4096,
        }

        return request_params

    def _make_request_with_retry(self, request_params: dict[str, Any], request_id: str) -> Message:
        """
        Make API request with retry logic.

        Args:
            request_params: Request parameters for the API
            request_id: Request ID for logging

        Returns:
            Anthropic Message response object

        Raises:
            LlmApiError: If request fails after all retries
        """
        last_exception: Exception | None = None
        start_time = time.time()

        for attempt in range(self.max_retries):
            try:
                logger.info(
                    f"Making Anthropic API request (attempt {attempt + 1}/{self.max_retries}) "
                    f"for request_id={request_id}"
                )

                # Make the API call
                response = self.client.messages.create(**request_params)

                # Log successful request with latency
                latency_ms = (time.time() - start_time) * 1000
                logger.info(
                    f"Anthropic API response: status=success, "
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
                    # Use retry_after from API if available, otherwise use exponential backoff
                    retry_after = getattr(e, "retry_after", None)
                    if retry_after is not None:
                        backoff = retry_after
                        logger.info(f"Following API 'retry_after' header, backing off {backoff}s")
                    else:
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
                        f"Client error from Anthropic API: {status_code} - {str(e)}"
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

    def _parse_response(self, api_response: Message, request_id: str) -> LlmResponseEnvelope:
        """
        Parse Anthropic API response into LlmResponseEnvelope.

        Args:
            api_response: Anthropic Message response object
            request_id: Request ID for correlation

        Returns:
            Parsed response envelope

        Raises:
            LlmApiError: If response cannot be parsed
        """
        try:
            # Extract text content from response
            # Anthropic Messages API returns content as a list of content blocks
            if not api_response.content:
                raise LlmApiError("Response contains no content")

            # Concatenate text from all text blocks
            text_parts = [
                block.text
                for block in api_response.content
                if hasattr(block, "text") and block.text
            ]
            text_content = "".join(text_parts)

            if not text_content:
                raise LlmApiError("Response content contains no text")

            # Extract usage information
            usage = {
                "prompt_tokens": api_response.usage.input_tokens if api_response.usage else 0,
                "completion_tokens": api_response.usage.output_tokens if api_response.usage else 0,
                "total_tokens": (
                    (api_response.usage.input_tokens + api_response.usage.output_tokens)
                    if api_response.usage
                    else 0
                ),
            }

            # Build metadata
            metadata = {
                "response_id": api_response.id,
                "model": api_response.model,
                "role": api_response.role,
                "stop_reason": api_response.stop_reason,
                "provider": "anthropic",
            }

            # Create response envelope
            return LlmResponseEnvelope(
                request_id=request_id,
                status="success",
                content=text_content,
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
        Generate a response from Anthropic Claude API.

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
            f"Generating Anthropic response for request_id={payload.request_id}, "
            f"model={self.model}, provider=anthropic"
        )

        try:
            # Build request parameters
            request_params = self._build_request_payload(payload)

            # Log request metadata (without full content)
            logger.info(
                f"Request metadata: model={request_params.get('model')}, "
                f"request_id={payload.request_id}, "
                f"max_tokens={request_params.get('max_tokens', 'default')}, "
                f"provider=anthropic"
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
                f"provider=anthropic, "
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
