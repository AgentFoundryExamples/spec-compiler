# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 45
- **Intra-repo dependencies**: 89
- **External stdlib dependencies**: 28
- **External third-party dependencies**: 27

## External Dependencies

### Standard Library / Core Modules

Total: 28 unique modules

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
- `queue.Queue`
- `random`
- `re`
- `sys`
- `tempfile`
- `threading`
- `threading.Lock`
- ... and 8 more (see JSON for full list)

### Third-Party Packages

Total: 27 unique packages

- `fastapi.APIRouter`
- `fastapi.FastAPI`
- `fastapi.HTTPException`
- `fastapi.Header`
- `fastapi.Request`
- `fastapi.Response`
- `fastapi.middleware.cors.CORSMiddleware`
- `fastapi.status`
- `fastapi.testclient.TestClient`
- `google.api_core.exceptions`
- `google.cloud.pubsub_v1`
- `google.oauth2.service_account`
- `httpx`
- `pydantic.BaseModel`
- `pydantic.Field`
- `pydantic.ValidationError`
- `pydantic.field_validator`
- `pydantic_settings.BaseSettings`
- `pydantic_settings.SettingsConfigDict`
- `pytest`
- ... and 7 more (see JSON for full list)

## Most Depended Upon Files (Intra-Repo)

- `src/spec_compiler/config.py` (15 dependents)
- `src/spec_compiler/models/__init__.py` (9 dependents)
- `src/spec_compiler/models/llm.py` (8 dependents)
- `src/spec_compiler/models/plan_status.py` (7 dependents)
- `src/spec_compiler/logging.py` (6 dependents)
- `src/spec_compiler/services/github_auth.py` (6 dependents)
- `src/spec_compiler/services/llm_client.py` (6 dependents)
- `src/spec_compiler/services/plan_scheduler_publisher.py` (6 dependents)
- `src/spec_compiler/services/github_repo.py` (5 dependents)
- `src/spec_compiler/models/compile.py` (4 dependents)

## Files with Most Dependencies (Intra-Repo)

- `src/spec_compiler/app/routes/compile.py` (9 dependencies)
- `src/spec_compiler/app/main.py` (6 dependencies)
- `src/spec_compiler/services/__init__.py` (6 dependencies)
- `src/spec_compiler/app/routes/health.py` (4 dependencies)
- `src/spec_compiler/services/openai_responses.py` (4 dependencies)
- `tests/test_compile_endpoint_llm_integration.py` (4 dependencies)
- `tests/test_compile_endpoint_repo_context.py` (4 dependencies)
- `src/spec_compiler/models/__init__.py` (3 dependencies)
- `src/spec_compiler/services/github_auth.py` (3 dependencies)
- `src/spec_compiler/services/llm_client.py` (3 dependencies)
