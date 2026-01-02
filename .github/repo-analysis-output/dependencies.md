# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 36
- **Intra-repo dependencies**: 61
- **External stdlib dependencies**: 26
- **External third-party dependencies**: 24

## External Dependencies

### Standard Library / Core Modules

Total: 26 unique modules

- `abc.ABC`
- `abc.abstractmethod`
- `base64`
- `collections.abc.AsyncGenerator`
- `contextlib.asynccontextmanager`
- `datetime.UTC`
- `datetime.datetime`
- `datetime.timedelta`
- `io.StringIO`
- `json`
- `logging`
- `os`
- `pathlib.Path`
- `re`
- `sys`
- `tempfile`
- `threading`
- `threading.Lock`
- `time`
- `typing.Annotated`
- ... and 6 more (see JSON for full list)

### Third-Party Packages

Total: 24 unique packages

- `fastapi.APIRouter`
- `fastapi.FastAPI`
- `fastapi.HTTPException`
- `fastapi.Header`
- `fastapi.Request`
- `fastapi.Response`
- `fastapi.middleware.cors.CORSMiddleware`
- `fastapi.status`
- `fastapi.testclient.TestClient`
- `httpx`
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
- ... and 4 more (see JSON for full list)

## Most Depended Upon Files (Intra-Repo)

- `src/spec_compiler/config.py` (10 dependents)
- `src/spec_compiler/models/__init__.py` (8 dependents)
- `src/spec_compiler/logging.py` (6 dependents)
- `src/spec_compiler/models/llm.py` (6 dependents)
- `src/spec_compiler/services/github_auth.py` (5 dependents)
- `src/spec_compiler/services/github_repo.py` (5 dependents)
- `src/spec_compiler/models/compile.py` (4 dependents)
- `src/spec_compiler/services/llm_client.py` (3 dependents)
- `src/spec_compiler/services/openai_responses.py` (3 dependents)
- `src/spec_compiler/app/routes/compile.py` (2 dependents)

## Files with Most Dependencies (Intra-Repo)

- `src/spec_compiler/app/main.py` (6 dependencies)
- `src/spec_compiler/app/routes/compile.py` (6 dependencies)
- `src/spec_compiler/services/__init__.py` (4 dependencies)
- `src/spec_compiler/services/openai_responses.py` (4 dependencies)
- `tests/test_compile_endpoint_repo_context.py` (4 dependencies)
- `src/spec_compiler/services/github_auth.py` (3 dependencies)
- `src/spec_compiler/services/llm_client.py` (3 dependencies)
- `tests/test_compile_endpoint.py` (3 dependencies)
- `tests/test_models_helpers.py` (3 dependencies)
- `tests/test_services_llm.py` (3 dependencies)
