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
LLM Client abstraction layer.

Provides an abstract base class for LLM client implementations with
provider selection, stub mode support, and error handling.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

from spec_compiler.config import settings
from spec_compiler.models.llm import LlmCompiledSpecOutput, LlmRequestEnvelope, LlmResponseEnvelope

logger = logging.getLogger(__name__)


class LlmClientError(Exception):
    """Base exception for LLM client errors."""

    pass


class LlmConfigurationError(LlmClientError):
    """Raised when LLM client configuration is invalid."""

    pass


class LlmApiError(LlmClientError):
    """Raised when LLM API call fails."""

    pass


class LlmClient(ABC):
    """
    Abstract base class for LLM clients.

    Defines the interface for generating responses from LLM providers.
    Implementations should handle provider-specific API calls, retries,
    timeouts, and error handling.
    """

    @abstractmethod
    def generate_response(self, payload: LlmRequestEnvelope) -> LlmResponseEnvelope:
        """
        Generate a response from the LLM.

        Args:
            payload: Request envelope containing all necessary data for the LLM call

        Returns:
            Response envelope with the LLM-generated content

        Raises:
            LlmConfigurationError: If the client is not properly configured
            LlmApiError: If the API call fails
        """
        pass


class StubLlmClient(LlmClient):
    """
    Stub LLM client for local development and testing.

    Returns pre-defined responses from sample.v1_1.json instead of making
    actual API calls. Useful for testing without consuming API quota.
    """

    def __init__(self, sample_file_path: str | None = None):
        """
        Initialize the stub LLM client.

        Args:
            sample_file_path: Optional path to sample JSON file. If not provided,
                            uses sample.v1_1.json from repository root.
        """
        self.sample_file_path = sample_file_path or self._get_default_sample_path()
        logger.info(f"StubLlmClient initialized with sample file: {self.sample_file_path}")

    def _get_default_sample_path(self) -> str:
        """
        Get the default path to sample.v1_1.json file.

        Returns:
            Absolute path to sample.v1_1.json
        """
        # Assume sample file is in repository root, relative to this file
        current_file = Path(__file__)
        repo_root = current_file.parent.parent.parent.parent
        sample_path = repo_root / "sample.v1_1.json"
        return str(sample_path.resolve())

    def generate_response(self, payload: LlmRequestEnvelope) -> LlmResponseEnvelope:
        """
        Generate a stub response from sample.v1_1.json.

        Args:
            payload: Request envelope (used for request_id correlation)

        Returns:
            Response envelope with parsed sample data

        Raises:
            LlmApiError: If sample file cannot be read or parsed
        """
        logger.info(f"Generating stub response for request_id={payload.request_id}")

        try:
            sample_path = Path(self.sample_file_path)

            if not sample_path.exists():
                raise LlmApiError(f"Sample file not found: {self.sample_file_path}")

            if not sample_path.is_file():
                raise LlmApiError(f"Sample path is not a file: {self.sample_file_path}")

            # Read and parse sample file
            sample_content = sample_path.read_text(encoding="utf-8")

            # Parse as LlmCompiledSpecOutput to validate structure
            compiled_output = LlmCompiledSpecOutput.from_json_string(sample_content)

            # Create synthetic response envelope
            response = LlmResponseEnvelope(
                request_id=payload.request_id,
                status="success",
                content=sample_content,
                model="stub-model",
                usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
                metadata={
                    "stub_mode": True,
                    "sample_file": self.sample_file_path,
                    "version": compiled_output.version,
                    "issue_count": len(compiled_output.issues),
                },
            )

            logger.info(
                f"Generated stub response for request_id={payload.request_id}, "
                f"version={compiled_output.version}, issues={len(compiled_output.issues)}"
            )

            return response

        except LlmApiError:
            raise
        except Exception as e:
            logger.error(f"Failed to generate stub response: {e}", exc_info=True)
            raise LlmApiError(f"Failed to read or parse sample file: {e}") from e


def create_llm_client(provider: str | None = None, stub_mode: bool | None = None) -> LlmClient:
    """
    Factory function to create an LLM client based on configuration.

    Args:
        provider: LLM provider to use ("openai", "anthropic"). If None, uses settings.llm_provider
        stub_mode: Whether to use stub mode. If None, uses settings.llm_stub_mode

    Returns:
        Configured LLM client instance

    Raises:
        LlmConfigurationError: If provider is not supported or configuration is invalid
    """
    # Use settings if not explicitly provided
    provider = (provider or settings.llm_provider).lower().strip()
    stub_mode = stub_mode if stub_mode is not None else settings.llm_stub_mode

    # If stub mode is enabled, return stub client regardless of provider
    if stub_mode:
        logger.info("Creating StubLlmClient (stub mode enabled)")
        return StubLlmClient()

    # Create provider-specific client
    if provider == "openai":
        logger.info("Creating OpenAI client")
        # Import here to avoid circular dependencies
        from spec_compiler.services.openai_responses import OpenAiResponsesClient

        return OpenAiResponsesClient()

    elif provider == "anthropic":
        logger.warning(
            "Anthropic provider requested but not yet implemented. "
            "Consider using stub mode for testing."
        )
        raise LlmConfigurationError(
            f"Provider '{provider}' is not yet implemented. "
            "Supported providers: openai. Use LLM_STUB_MODE=true for testing."
        )

    else:
        raise LlmConfigurationError(
            f"Unknown LLM provider: '{provider}'. Supported providers: openai, anthropic"
        )
