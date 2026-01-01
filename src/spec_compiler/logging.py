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
Structured logging configuration for Cloud Run compatibility.

Provides JSON logging with severity, timestamp, trace, and correlation IDs.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import EventDict, Processor

from spec_compiler.config import settings


def add_severity_field(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
    """
    Add Google Cloud severity field to log entries.

    Maps standard log levels to Cloud Logging severity levels.
    """
    level = event_dict.get("level", "").upper()
    severity_map = {
        "DEBUG": "DEBUG",
        "INFO": "INFO",
        "WARNING": "WARNING",
        "ERROR": "ERROR",
        "CRITICAL": "CRITICAL",
    }
    event_dict["severity"] = severity_map.get(level, "DEFAULT")
    return event_dict


def configure_logging() -> None:
    """
    Configure structured logging for the application.

    Sets up JSON logging for Cloud Run when LOG_JSON is enabled,
    otherwise uses console logging for development.
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )

    # Shared processors for all configurations
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.log_json:
        # JSON logging for Cloud Run
        processors = shared_processors + [
            add_severity_field,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console logging for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """
    Get a configured logger instance.

    Args:
        name: Logger name, typically __name__

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


# Configure logging on module import
configure_logging()
