"""
Health check endpoint.

Provides readiness and liveness probe for Cloud Run and Kubernetes.
"""

from fastapi import APIRouter

from spec_compiler.logging import get_logger

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
