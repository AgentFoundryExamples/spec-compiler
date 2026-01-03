# Dependency Graph

Multi-language intra-repository dependency analysis.

Supports Python, JavaScript/TypeScript, C/C++, Rust, Go, Java, C#, Swift, HTML/CSS, and SQL.

Includes classification of external dependencies as stdlib vs third-party.

## Statistics

- **Total files**: 50
- **Intra-repo dependencies**: 103
- **External stdlib dependencies**: 28
- **External third-party dependencies**: 42

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

Total: 42 unique packages

- `anthropic.APIError`
- `anthropic.APITimeoutError`
- `anthropic.Anthropic`
- `anthropic.RateLimitError`
- `anthropic.types.Message`
- `anthropic.types.Usage`
- `anthropic.types.content_block.ContentBlock`
- `fastapi.APIRouter`
- `fastapi.BackgroundTasks`
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
- ... and 22 more (see JSON for full list)

## Most Depended Upon Files (Intra-Repo)

- `src/spec_compiler/config.py` (16 dependents)
- `src/spec_compiler/models/__init__.py` (10 dependents)
- `src/spec_compiler/services/llm_client.py` (10 dependents)
- `src/spec_compiler/models/llm.py` (10 dependents)
- `src/spec_compiler/models/plan_status.py` (7 dependents)
- `src/spec_compiler/logging.py` (6 dependents)
- `src/spec_compiler/services/github_auth.py` (6 dependents)
- `src/spec_compiler/services/plan_scheduler_publisher.py` (6 dependents)
- `src/spec_compiler/services/github_repo.py` (5 dependents)
- `src/spec_compiler/models/compile.py` (4 dependents)

## Files with Most Dependencies (Intra-Repo)

- `src/spec_compiler/app/routes/compile.py` (10 dependencies)
- `src/spec_compiler/app/main.py` (6 dependencies)
- `src/spec_compiler/services/__init__.py` (6 dependencies)
- `src/spec_compiler/app/routes/health.py` (4 dependencies)
- `src/spec_compiler/services/llm_client.py` (4 dependencies)
- `src/spec_compiler/services/openai_responses.py` (4 dependencies)
- `tests/test_compile_endpoint_llm_integration.py` (4 dependencies)
- `tests/test_compile_endpoint_repo_context.py` (4 dependencies)
- `tests/test_services_llm.py` (4 dependencies)
- `src/spec_compiler/models/__init__.py` (3 dependencies)
