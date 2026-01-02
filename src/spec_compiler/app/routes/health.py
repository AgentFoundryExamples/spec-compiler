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
Health check endpoint.

Provides readiness and liveness probe for Cloud Run and Kubernetes.
Also includes debug endpoints for testing (local development only).
"""

from fastapi import APIRouter, HTTPException, status

from spec_compiler.config import settings
from spec_compiler.logging import get_logger
from spec_compiler.models.plan_status import PlanStatusMessage
from spec_compiler.services.plan_scheduler_publisher import (
    ConfigurationError,
    PlanSchedulerPublisher,
)

router = APIRouter()
logger = get_logger(__name__)


@router.get("/health")
async def health_check() -> dict[str, str]:
    """
    Health check endpoint.

    Returns a simple status indicator for container orchestration systems.

    Returns:
        Dictionary with status "ok"
    """
    logger.debug("Health check requested")
    return {"status": "ok"}


@router.post("/debug/status")
async def debug_publish_status() -> dict[str, str | int]:
    """
    Debug endpoint to test status message publishing.

    Only available in development environments for safety.
    Publishes a sample status message to verify Pub/Sub configuration.

    Returns:
        Dictionary with status and message

    Raises:
        HTTPException: 403 if not in development environment
        HTTPException: 500 if publisher configuration is invalid
        HTTPException: 503 if publish fails
    """
    # Only allow in development environment
    if settings.app_env != "development":
        logger.warning(
            "Debug status endpoint accessed in non-development environment",
            app_env=settings.app_env,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Debug endpoints are only enabled in development environment",
        )

    logger.info("Debug status publish requested")

    # Try to create publisher
    try:
        publisher = PlanSchedulerPublisher(
            gcp_project_id=settings.gcp_project_id,
            topic_name=settings.pubsub_topic_plan_status,
            credentials_path=settings.pubsub_credentials_path,
        )
    except ConfigurationError as e:
        logger.error("Publisher configuration error", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "publisher_not_configured",
                "message": str(e),
            },
        ) from None
    except Exception as e:
        logger.error("Failed to initialize publisher", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "publisher_init_failed",
                "message": str(e),
            },
        ) from None

    # Create and publish test message
    try:
        test_message = PlanStatusMessage(
            plan_id="debug-test-plan",
            spec_index=0,
            status="in_progress",
            request_id="debug-test-request",
        )
        publisher.publish_status(test_message)

        logger.info("Debug status message published successfully")
        return {
            "status": "published",
            "message": "Test status message published successfully",
            "plan_id": test_message.plan_id,
            "spec_index": test_message.spec_index,
        }
    except Exception as e:
        logger.error("Failed to publish debug status message", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "publish_failed",
                "message": str(e),
            },
        ) from None
