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
Services package for spec-compiler.

Provides GitHub authentication, repository access, and LLM clients.
"""

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
    LlmClientError,
    LlmConfigurationError,
    StubLlmClient,
    create_llm_client,
)
from spec_compiler.services.openai_responses import OpenAiResponsesClient
from spec_compiler.services.plan_scheduler_publisher import (
    ConfigurationError,
    PlanSchedulerPublisher,
)

__all__ = [
    "GitHubAuthClient",
    "MintingError",
    "GitHubRepoClient",
    "GitHubFileError",
    "InvalidJSONError",
    "create_fallback_tree",
    "create_fallback_dependencies",
    "create_fallback_file_summaries",
    "LlmClient",
    "LlmClientError",
    "LlmConfigurationError",
    "LlmApiError",
    "StubLlmClient",
    "OpenAiResponsesClient",
    "create_llm_client",
    "PlanSchedulerPublisher",
    "ConfigurationError",
]
