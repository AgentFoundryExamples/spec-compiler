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
Tests for downstream sender abstraction.

Validates the DownstreamSender protocol, DefaultDownstreamLoggerSender implementation,
and factory functions.
"""

import pytest

from spec_compiler.models.llm import LlmCompiledSpecOutput
from spec_compiler.services.downstream_sender import (
    DefaultDownstreamLoggerSender,
    DownstreamSender,
    DownstreamSenderError,
    DownstreamValidationError,
)


def test_downstream_sender_is_abstract():
    """Test that DownstreamSender cannot be instantiated directly."""
    with pytest.raises(TypeError):
        DownstreamSender()  # type: ignore[abstract]


def test_default_downstream_logger_sender_initialization():
    """Test that DefaultDownstreamLoggerSender can be initialized."""
    sender = DefaultDownstreamLoggerSender()
    assert sender.downstream_target_uri == "placeholder://downstream/target"
    assert sender.skip_send is False


def test_default_downstream_logger_sender_with_custom_uri():
    """Test initialization with custom downstream target URI."""
    sender = DefaultDownstreamLoggerSender(downstream_target_uri="pubsub://my-project/my-topic")
    assert sender.downstream_target_uri == "pubsub://my-project/my-topic"
    assert sender.skip_send is False


def test_default_downstream_logger_sender_with_skip_flag():
    """Test initialization with skip_send flag enabled."""
    sender = DefaultDownstreamLoggerSender(skip_send=True)
    assert sender.skip_send is True


def test_send_compiled_spec_with_valid_context(caplog):
    """Test sending with all required context fields present."""
    sender = DefaultDownstreamLoggerSender(downstream_target_uri="test://target")

    output = LlmCompiledSpecOutput(version="1.0", issues=[{"title": "Test Issue"}])

    context = {
        "plan_id": "test-plan-123",
        "spec_index": 0,
        "request_id": "req-456",
        "github_owner": "test-owner",
        "github_repo": "test-repo",
    }

    # Should not raise any exceptions
    sender.send_compiled_spec(output, context)

    # Verify log was emitted with correct context
    assert "Downstream send attempt" in caplog.text
    assert "test-plan-123" in caplog.text
    assert "test://target" in caplog.text


def test_send_compiled_spec_without_optional_fields(caplog):
    """Test sending with only required context fields (no github metadata)."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])

    context = {
        "plan_id": "plan-789",
        "spec_index": 5,
        "request_id": "req-abc",
    }

    # Should not raise any exceptions
    sender.send_compiled_spec(output, context)

    # Verify log was emitted
    assert "Downstream send attempt" in caplog.text


def test_send_compiled_spec_missing_plan_id():
    """Test that missing plan_id raises DownstreamValidationError."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "spec_index": 0,
        "request_id": "req-123",
    }

    with pytest.raises(DownstreamValidationError) as exc_info:
        sender.send_compiled_spec(output, context)

    assert "plan_id" in str(exc_info.value)


def test_send_compiled_spec_missing_spec_index():
    """Test that missing spec_index raises DownstreamValidationError."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "plan_id": "plan-123",
        "request_id": "req-123",
    }

    with pytest.raises(DownstreamValidationError) as exc_info:
        sender.send_compiled_spec(output, context)

    assert "spec_index" in str(exc_info.value)


def test_send_compiled_spec_missing_request_id():
    """Test that missing request_id raises DownstreamValidationError."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "plan_id": "plan-123",
        "spec_index": 0,
    }

    with pytest.raises(DownstreamValidationError) as exc_info:
        sender.send_compiled_spec(output, context)

    assert "request_id" in str(exc_info.value)


def test_send_compiled_spec_empty_plan_id():
    """Test that empty plan_id raises DownstreamValidationError."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "plan_id": "",
        "spec_index": 0,
        "request_id": "req-123",
    }

    with pytest.raises(DownstreamValidationError) as exc_info:
        sender.send_compiled_spec(output, context)

    assert "plan_id" in str(exc_info.value)


def test_send_compiled_spec_whitespace_plan_id():
    """Test that whitespace-only plan_id raises DownstreamValidationError."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "plan_id": "   ",
        "spec_index": 0,
        "request_id": "req-123",
    }

    with pytest.raises(DownstreamValidationError) as exc_info:
        sender.send_compiled_spec(output, context)

    assert "plan_id" in str(exc_info.value)


def test_send_compiled_spec_empty_request_id():
    """Test that empty request_id raises DownstreamValidationError."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "plan_id": "plan-123",
        "spec_index": 0,
        "request_id": "",
    }

    with pytest.raises(DownstreamValidationError) as exc_info:
        sender.send_compiled_spec(output, context)

    assert "request_id" in str(exc_info.value)


def test_send_compiled_spec_negative_spec_index():
    """Test that negative spec_index raises DownstreamValidationError."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "plan_id": "plan-123",
        "spec_index": -1,
        "request_id": "req-123",
    }

    with pytest.raises(DownstreamValidationError) as exc_info:
        sender.send_compiled_spec(output, context)

    assert "spec_index" in str(exc_info.value)


def test_send_compiled_spec_non_integer_spec_index():
    """Test that non-integer spec_index raises DownstreamValidationError."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "plan_id": "plan-123",
        "spec_index": "0",  # String instead of int
        "request_id": "req-123",
    }

    with pytest.raises(DownstreamValidationError) as exc_info:
        sender.send_compiled_spec(output, context)

    assert "spec_index" in str(exc_info.value)


def test_send_compiled_spec_with_skip_flag_enabled(caplog):
    """Test that skip_send=True logs skip reason instead of attempting send."""
    sender = DefaultDownstreamLoggerSender(skip_send=True)

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "plan_id": "plan-123",
        "spec_index": 0,
        "request_id": "req-123",
    }

    # Should not raise any exceptions
    sender.send_compiled_spec(output, context)

    # Verify skip was logged
    assert "Downstream send skipped" in caplog.text
    assert "SKIP_DOWNSTREAM_SEND=true" in caplog.text
    assert "feature_flag_disabled" in caplog.text


def test_send_compiled_spec_logs_spec_metadata(caplog):
    """Test that spec version and issue count are logged."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(
        version="af/1.1",
        issues=[
            {"title": "Issue 1"},
            {"title": "Issue 2"},
            {"title": "Issue 3"},
        ],
    )

    context = {
        "plan_id": "plan-123",
        "spec_index": 0,
        "request_id": "req-123",
    }

    sender.send_compiled_spec(output, context)

    # Verify metadata is logged
    assert "af/1.1" in caplog.text
    # Issue count should be logged as part of structured logs


def test_send_compiled_spec_logs_repo_metadata(caplog):
    """Test that repository metadata is included when present."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "plan_id": "plan-123",
        "spec_index": 0,
        "request_id": "req-123",
        "github_owner": "test-org",
        "github_repo": "test-repo",
    }

    sender.send_compiled_spec(output, context)

    # Verify repo metadata is logged
    assert "test-org" in caplog.text
    assert "test-repo" in caplog.text


def test_downstream_sender_error_inheritance():
    """Test that error classes have proper inheritance."""
    assert issubclass(DownstreamSenderError, Exception)
    assert issubclass(DownstreamValidationError, DownstreamSenderError)


def test_send_compiled_spec_multiple_missing_fields():
    """Test that all missing required fields are reported."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {}  # All fields missing

    with pytest.raises(DownstreamValidationError) as exc_info:
        sender.send_compiled_spec(output, context)

    error_msg = str(exc_info.value)
    assert "plan_id" in error_msg
    assert "spec_index" in error_msg
    assert "request_id" in error_msg


def test_send_compiled_spec_spec_index_zero():
    """Test that spec_index=0 is valid (edge case for non-negative validation)."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "plan_id": "plan-123",
        "spec_index": 0,
        "request_id": "req-123",
    }

    # Should not raise any exceptions
    sender.send_compiled_spec(output, context)


def test_send_compiled_spec_large_spec_index():
    """Test that large spec_index values are handled correctly."""
    sender = DefaultDownstreamLoggerSender()

    output = LlmCompiledSpecOutput(version="1.0", issues=[])
    context = {
        "plan_id": "plan-123",
        "spec_index": 99999,
        "request_id": "req-123",
    }

    # Should not raise any exceptions
    sender.send_compiled_spec(output, context)
