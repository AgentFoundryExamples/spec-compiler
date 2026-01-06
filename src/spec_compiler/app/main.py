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
from fastapi.openapi.utils import get_openapi

from spec_compiler.app.routes import compile, health
from spec_compiler.config import settings
from spec_compiler.logging import get_logger
from spec_compiler.middleware.error_handler import ErrorHandlingMiddleware
from spec_compiler.middleware.request_id import RequestIdMiddleware
from spec_compiler.models.compile import CompileRequest, CompileSpec

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
    app.include_router(compile.router, tags=["compile"])

    # Customize OpenAPI schema to include CompileRequest and CompileSpec
    # NOTE: This custom function ensures CompileSpec is properly referenced
    # in the main components/schemas section rather than nested in $defs,
    # which improves SDK generation compatibility.
    # 
    # To regenerate the OpenAPI schema after model changes:
    # 1. Ensure dependencies are installed: pip install -r requirements.txt
    # 2. Run: PYTHONPATH=src python -c "from spec_compiler.app.main import app; import json; print(json.dumps(app.openapi(), indent=2))" > spec-compiler.openapi.json
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        schemas = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
        
        # Get Pydantic schema for CompileSpec and CompileRequest
        compile_spec_schema = CompileSpec.model_json_schema()
        compile_request_schema = CompileRequest.model_json_schema()
        
        # Pydantic v2 may nest schemas in $defs. Move CompileSpec to the top level for better client generation.
        if "$defs" in compile_request_schema and "CompileSpec" in compile_request_schema["$defs"]:
            # Move the definition
            schemas["CompileSpec"] = compile_request_schema["$defs"]["CompileSpec"]
            
            # Update the reference
            spec_property = compile_request_schema.get("properties", {}).get("spec")
            if spec_property and "$ref" in spec_property:
                spec_property["$ref"] = "#/components/schemas/CompileSpec"
            
            # Clean up the now-empty $defs
            del compile_request_schema["$defs"]
        else:
            # Add CompileSpec directly if not in $defs
            schemas["CompileSpec"] = compile_spec_schema
        
        # Add CompileRequest schema
        schemas["CompileRequest"] = compile_request_schema

        app.openapi_schema = openapi_schema
        return app.openapi_schema
    
    app.openapi = custom_openapi  # type: ignore[method-assign]

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
