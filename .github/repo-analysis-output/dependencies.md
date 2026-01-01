# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 14
- **Intra-repo dependencies**: 9
- **External stdlib dependencies**: 8
- **External third-party dependencies**: 16

## External Dependencies

### Standard Library / Core Modules

Total: 8 unique modules

- `collections.abc.AsyncGenerator`
- `contextlib.asynccontextmanager`
- `logging`
- `os`
- `sys`
- `typing.Any`
- `unittest.mock.patch`
- `uuid`

### Third-Party Packages

Total: 16 unique packages

- `fastapi.APIRouter`
- `fastapi.FastAPI`
- `fastapi.Request`
- `fastapi.Response`
- `fastapi.middleware.cors.CORSMiddleware`
- `fastapi.testclient.TestClient`
- `pydantic.Field`
- `pydantic_settings.BaseSettings`
- `pydantic_settings.SettingsConfigDict`
- `pytest`
- `starlette.middleware.base.BaseHTTPMiddleware`
- `starlette.middleware.base.RequestResponseEndpoint`
- `structlog`
- `structlog.types.EventDict`
- `structlog.types.Processor`
- `uvicorn`

## Most Depended Upon Files (Intra-Repo)

- `src/spec_compiler/config.py` (4 dependents)
- `src/spec_compiler/logging.py` (2 dependents)
- `src/spec_compiler/app/routes/health.py` (1 dependents)
- `src/spec_compiler/middleware/request_id.py` (1 dependents)
- `src/spec_compiler/app/main.py` (1 dependents)

## Files with Most Dependencies (Intra-Repo)

- `src/spec_compiler/app/main.py` (4 dependencies)
- `src/spec_compiler/app/routes/health.py` (1 dependencies)
- `src/spec_compiler/logging.py` (1 dependencies)
- `src/spec_compiler/middleware/request_id.py` (1 dependencies)
- `tests/conftest.py` (1 dependencies)
- `tests/test_config.py` (1 dependencies)
