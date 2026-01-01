# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 22
- **Intra-repo dependencies**: 21
- **External stdlib dependencies**: 11
- **External third-party dependencies**: 20

## External Dependencies

### Standard Library / Core Modules

Total: 11 unique modules

- `collections.abc.AsyncGenerator`
- `contextlib.asynccontextmanager`
- `io.StringIO`
- `json`
- `logging`
- `os`
- `sys`
- `typing.Any`
- `typing.Literal`
- `unittest.mock.patch`
- `uuid`

### Third-Party Packages

Total: 20 unique packages

- `fastapi.APIRouter`
- `fastapi.FastAPI`
- `fastapi.Request`
- `fastapi.Response`
- `fastapi.middleware.cors.CORSMiddleware`
- `fastapi.testclient.TestClient`
- `pydantic.BaseModel`
- `pydantic.Field`
- `pydantic.ValidationError`
- `pydantic.field_validator`
- `pydantic_settings.BaseSettings`
- `pydantic_settings.SettingsConfigDict`
- `pytest`
- `starlette.middleware.base.BaseHTTPMiddleware`
- `starlette.middleware.base.RequestResponseEndpoint`
- `starlette.responses.JSONResponse`
- `structlog`
- `structlog.types.EventDict`
- `structlog.types.Processor`
- `uvicorn`

## Most Depended Upon Files (Intra-Repo)

- `src/spec_compiler/config.py` (4 dependents)
- `src/spec_compiler/logging.py` (3 dependents)
- `src/spec_compiler/models/llm.py` (3 dependents)
- `src/spec_compiler/models/__init__.py` (2 dependents)
- `src/spec_compiler/middleware/error_handler.py` (2 dependents)
- `src/spec_compiler/middleware/request_id.py` (2 dependents)
- `src/spec_compiler/models/compile.py` (2 dependents)
- `src/spec_compiler/app/routes/health.py` (1 dependents)
- `src/spec_compiler/app/main.py` (1 dependents)
- `src/spec_compiler/__init__.py` (1 dependents)

## Files with Most Dependencies (Intra-Repo)

- `src/spec_compiler/app/main.py` (5 dependencies)
- `tests/test_models_helpers.py` (3 dependencies)
- `src/spec_compiler/middleware/__init__.py` (2 dependencies)
- `src/spec_compiler/models/__init__.py` (2 dependencies)
- `src/spec_compiler/__init__.py` (1 dependencies)
- `src/spec_compiler/app/routes/health.py` (1 dependencies)
- `src/spec_compiler/logging.py` (1 dependencies)
- `src/spec_compiler/middleware/request_id.py` (1 dependencies)
- `tests/conftest.py` (1 dependencies)
- `tests/test_config.py` (1 dependencies)
