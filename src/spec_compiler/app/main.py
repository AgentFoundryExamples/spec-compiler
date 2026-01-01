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
FastAPI application factory and main entry point.

Creates and configures the FastAPI application with middleware,
routes, and CORS settings.
"""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from spec_compiler.app.routes import health
from spec_compiler.config import settings
from spec_compiler.logging import get_logger
from spec_compiler.middleware.error_handler import ErrorHandlingMiddleware
from spec_compiler.middleware.request_id import RequestIdMiddleware

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Lifespan context manager for startup and shutdown events.

    Args:
        app: FastAPI application instance

    Yields:
        None during application runtime
    """
    # Startup
    logger.info(
        "Starting Spec Compiler Service",
        version=settings.app_version,
        environment=settings.app_env,
        port=settings.port,
    )
    yield
    # Shutdown
    logger.info("Shutting down Spec Compiler Service")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="Spec Compiler Service",
        description="FastAPI service for compiling specifications with LLM integrations",
        version=settings.app_version,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Add error handling middleware (outermost, catches all exceptions)
    app.add_middleware(ErrorHandlingMiddleware)

    # Add request ID middleware
    app.add_middleware(RequestIdMiddleware)

    # Configure CORS if origins are specified
    cors_origins = settings.cors_origins_list
    if cors_origins:
        logger.info("Configuring CORS", origins=cors_origins)
        # Don't allow credentials with wildcard origins (security risk)
        allow_credentials = "*" not in cors_origins
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=allow_credentials,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Include routers
    app.include_router(health.router, tags=["health"])

    # Version endpoint
    @app.get("/version", tags=["info"])
    async def version_info() -> dict[str, str]:
        """
        Return application version information.

        Returns git SHA if available from environment, otherwise returns
        the configured APP_VERSION.
        """
        git_sha = os.getenv("GIT_SHA", settings.app_version)
        return {
            "version": settings.app_version,
            "git_sha": git_sha,
            "environment": settings.app_env,
        }

    return app


# Create application instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "spec_compiler.app.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )
