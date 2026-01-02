# Spec Compiler Service

A FastAPI service for compiling specifications with LLM integrations. This service provides a robust foundation with health checks, structured logging, request tracing, and observability features designed for Cloud Run deployment.

## Features

- **FastAPI Framework**: Modern async Python web framework with automatic OpenAPI documentation
- **Structured Logging**: JSON-formatted logs compatible with Google Cloud Logging
- **Request Tracing**: Automatic request ID propagation for distributed tracing
- **Error Handling**: Uniform error responses with request correlation for debugging
- **Health Endpoints**: Standard health check and version endpoints for orchestration
- **CORS Support**: Configurable CORS middleware
- **Configuration Management**: Environment-based settings with sensible defaults
- **Testing**: Comprehensive test suite with pytest

## Quick Start

### Prerequisites

- Python 3.11 or higher
- pip for package management
- Virtual environment tool (venv, included with Python 3.11+)

**Note**: These instructions work on macOS, Linux, and Windows. On Windows, use `python` instead of `python3`. The virtual environment activation command depends on your shell:
- **Command Prompt**: `venv\Scripts\activate`
- **PowerShell**: `.\venv\Scripts\Activate.ps1`
- **Git Bash**: `source venv/Scripts/activate`

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd spec-compiler
```

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your configuration
```

**⚠️ Security Warning**: Never commit your `.env` file or any file containing real secrets to version control. The `.env` file is already in `.gitignore` to prevent accidental commits. Always use `.env.example` as a template and keep actual secrets local only. You can verify your .env is ignored by running `git status --ignored`.

### Running the Service

Start the development server with environment variables loaded from `.env`:

```bash
# The application automatically loads .env via python-dotenv (configured in config.py)
# On macOS/Linux:
PYTHONPATH=src python -m uvicorn spec_compiler.app.main:app --host 0.0.0.0 --port 8080 --reload

# On Windows (Command Prompt):
set PYTHONPATH=src && python -m uvicorn spec_compiler.app.main:app --host 0.0.0.0 --port 8080 --reload

# On Windows (PowerShell):
$env:PYTHONPATH="src"; python -m uvicorn spec_compiler.app.main:app --host 0.0.0.0 --port 8080 --reload
```

**How Environment Variables are Loaded**:
- The `python-dotenv` package is included in `requirements.txt`
- Environment variables are automatically loaded from `.env` file when the application starts (see `config.py`)
- You can override any `.env` value by setting it explicitly in your shell (e.g., `PORT=3000 PYTHONPATH=src python -m uvicorn ...`)
- The `APP_ENV` variable controls behavior (development mode enables auto-reload and verbose logging)

The service will be available at:
- API: http://localhost:8080
- Interactive API docs (Swagger UI): http://localhost:8080/docs
- OpenAPI schema: http://localhost:8080/openapi.json
- Health check: http://localhost:8080/health
- Version info: http://localhost:8080/version

### Testing

Run the test suite:
```bash
pytest
```

Run with coverage:
```bash
pytest --cov=src/spec_compiler --cov-report=html
```

### Code Quality

Format code with Black:
```bash
black src/ tests/
```

Lint with Ruff:
```bash
ruff check src/ tests/
```

Type check with mypy:
```bash
mypy src/
```

### Pre-commit Hooks (Optional)

Pre-commit hooks are available to automatically run formatting and linting checks before each commit:

```bash
# Install pre-commit
pip install pre-commit

# Install the git hooks
pre-commit install

# Run manually on all files (optional)
pre-commit run --all-files
```

The pre-commit hooks will automatically run black, ruff, and pytest before each commit.

### Continuous Integration

This project uses GitHub Actions for continuous integration. On every pull request and push to main, the CI workflow will:

- Install Python 3.11 and dependencies
- Run black formatting checks
- Run ruff linting checks  
- Run the full test suite with coverage reporting

See `.github/workflows/ci.yml` for the complete CI configuration.

## Configuration

All configuration is managed through environment variables. Copy `.env.example` to `.env` and customize as needed.

### Environment Variables Reference

The following environment variables are available (see `.env.example` for a complete template):

#### Application Settings
- **`APP_ENV`**: Application environment (`development`, `staging`, `production`). Controls logging verbosity and auto-reload behavior.
- **`PORT`**: Server port (default: `8080`). Cloud Run will automatically set this when deployed.
- **`APP_VERSION`**: Application version string (default: `0.1.0`). Can also use git SHA.

#### API Keys (Optional - Not Required for Core Functionality)
- **`OPENAI_API_KEY`**: OpenAI API key for GPT models (format: `sk-...`). **Not yet used** - reserved for future LLM integrations.
- **`CLAUDE_API_KEY`**: Anthropic API key for Claude models (format: `sk-ant-...`). **Not yet used** - reserved for future LLM integrations.

#### Google Cloud Configuration (Optional)
- **`GCP_PROJECT_ID`**: Google Cloud Project ID. **Not yet used** - reserved for future integrations.
- **`PUBSUB_TOPIC_PLAN_STATUS`**: Pub/Sub topic name for plan status updates. **Not yet used** - reserved for future Pub/Sub integrations.
- **`DOWNSTREAM_LOG_SINK`**: Downstream log sink for Cloud Logging. **Not yet used** - reserved for future logging integrations.

#### CORS Settings
- **`CORS_ORIGINS`**: Comma-separated list of allowed CORS origins (e.g., `http://localhost:3000,https://example.com`). Leave empty to disable CORS, or use `*` for all origins (not recommended in production).

#### Logging Configuration
- **`LOG_LEVEL`**: Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). Default: `INFO`.
- **`LOG_JSON`**: Enable JSON structured logging (`true`/`false`). Default: `true`. Should be `true` for Cloud Run deployments to integrate with Google Cloud Logging.

#### Request Configuration
- **`REQUEST_ID_HEADER`**: HTTP header name for request correlation (default: `X-Request-Id`). Used for distributed tracing.
- **`MAX_REQUEST_BODY_SIZE_BYTES`**: Maximum request body size in bytes (default: `10485760` = 10MB). Requests exceeding this limit will be rejected with HTTP 413.
- **`MAX_IDEMPOTENCY_KEY_LENGTH`**: Maximum idempotency key length (default: `100`). Keys exceeding this length are truncated for security.

#### GitHub API Configuration
- **`GITHUB_API_BASE_URL`**: Base URL for GitHub REST API (default: `https://api.github.com`). Override for GitHub Enterprise or testing against mock servers.
- **`MINTING_SERVICE_BASE_URL`**: Base URL for the GitHub token minting service. This should be the Cloud Run service URL where the minting service is deployed (e.g., `https://github-token-service-xxxxx-uc.a.run.app`). **Required for GitHub API calls**.
- **`MINTING_SERVICE_AUTH_HEADER`**: Optional authorization header value for authenticating with the minting service. For Cloud Run IAM authentication, this should be a GCP identity token obtained via `gcloud auth print-identity-token` or programmatically via `google.oauth2.id_token.fetch_id_token()`.

**⚠️ Important Notes**:
- GitHub integration, LLM API calls, and Pub/Sub messaging are **not yet implemented**. The corresponding environment variables are placeholders for future features.
- Never commit real API keys, tokens, or secrets to version control. Always use `.env` for local secrets (already in `.gitignore`).
- For production deployments, use your platform's secret management system (e.g., Google Cloud Secret Manager, AWS Secrets Manager).

### GitHub Token Minting Workflow

The service is designed to integrate with a GitHub App token minting service for obtaining user-to-server access tokens. Here's how the workflow is intended to work:

#### Prerequisites

1. **Minting Service Deployment**: Deploy the GitHub App token minting service (defined by `github-app-basic.openapi.json`) to Cloud Run or another container platform.
2. **OAuth Configuration**: Complete the GitHub App OAuth flow via the minting service's `/github/install` endpoint to obtain and store a user access token.
3. **IAM Permissions**: Ensure the spec-compiler service has appropriate IAM permissions to invoke the minting service (requires `roles/run.invoker` for Cloud Run).

#### Token Acquisition

When the compile service needs to interact with GitHub (e.g., to fetch repository context), it will:

1. **Request Token**: Call `POST {MINTING_SERVICE_BASE_URL}/api/token` with an optional `force_refresh` parameter.
2. **Authentication**: Include the `MINTING_SERVICE_AUTH_HEADER` value in the `Authorization: Bearer <token>` header (GCP identity token for Cloud Run IAM auth).
3. **Receive Token**: The minting service returns a `TokenResponse` with:
   - `access_token`: GitHub user access token (format: `gho_...`)
   - `token_type`: Typically `"bearer"`
   - `expires_at`: ISO-8601 expiration timestamp or `null` for non-expiring tokens

#### Token Response Format

Based on `github-app-basic.openapi.json`, the minting service returns:

```json
{
  "access_token": "gho_ExampleToken123...",
  "token_type": "bearer",
  "expires_at": "2025-12-31T23:59:59+00:00"  // or null
}
```

#### Configuration Validation

The `Settings.validate_github_config()` method can be used to verify GitHub configuration at startup:

```python
from spec_compiler.config import settings

validation = settings.validate_github_config()
# Returns: {
#   'github_api_url': 'ok' | 'missing' | 'invalid',
#   'minting_service_url': 'ok' | 'missing' | 'invalid',
#   'minting_auth_configured': 'yes' | 'no'
# }
```

#### Data Models

The service defines the following models for GitHub token handling:

- **`GitHubAuthToken`**: Represents a minted GitHub token with metadata (access_token, token_type, expires_at, scope, created_at)
- **`RepoContextPayload`**: Represents repository context data (tree, dependencies, file_summaries) to be passed to LLM requests

#### Error Handling

- **Missing Configuration**: If `MINTING_SERVICE_BASE_URL` is not configured, GitHub API calls will fail early with a configuration error rather than during request processing.
- **Invalid URL**: The validation method detects malformed URLs (non-http/https schemes) before attempting requests.
- **Token Expiry**: The minting service automatically refreshes tokens when they're near expiration (configurable threshold).
- **Authentication Failure**: If the minting service returns 401/403, check IAM permissions and identity token validity.

#### Operational Assumptions

1. **Stateless Service**: The spec-compiler service does not store tokens. It requests them from the minting service on-demand.
2. **Token Refresh**: The minting service handles token refresh logic and expiry tracking via Firestore.
3. **IAM Authentication**: All minting service calls require Cloud Run IAM authentication via GCP identity tokens.
4. **Single User Context**: The current minting service design supports a single-user OAuth token (not multi-tenant).

#### Future Implementation

When implementing actual GitHub API integration:

1. Call the minting service to obtain a fresh token
2. Use the token in GitHub API requests via `Authorization: Bearer {access_token}`
3. Handle token expiry by requesting a new token with `force_refresh=true`
4. Pass repository context (tree, dependencies, file_summaries) to LLM compilation requests

## API Endpoints

### Compile
- **`POST /compile-spec`**: Compile a specification with LLM integration. Accepts a `CompileRequest` JSON payload and optional `Idempotency-Key` header. Returns HTTP 202 Accepted with a `CompileResponse` containing request tracking information. Currently stubs downstream LLM integration.

### Health & Monitoring
- **`GET /health`**: Health check endpoint returning `{"status": "ok"}`. Used by Cloud Run and Docker health checks.
- **`GET /version`**: Version information including app version, git SHA (if available), and environment.

### Documentation
- **`GET /docs`**: Interactive API documentation (Swagger UI). Automatically generated from OpenAPI schema.
- **`GET /openapi.json`**: OpenAPI specification in JSON format. Use this for code generation or API clients.

## API Models and Contracts

The service defines typed Pydantic models for the compile API contract and internal LLM envelopes.

### Compile API Models

#### CompileRequest

The request model for the compile endpoint with validation:

```python
{
    "plan_id": str,           # Non-empty plan identifier
    "spec_index": int,        # Specification index (>= 0)
    "spec_data": dict | list, # Arbitrary JSON specification data
    "github_owner": str,      # Non-empty GitHub repository owner
    "github_repo": str        # Non-empty GitHub repository name
}
```

**Validation Rules:**
- `plan_id`, `github_owner`, and `github_repo` must be non-empty and cannot be whitespace-only
- `spec_index` must be >= 0 (zero-based indexing)
- `spec_data` accepts both dict and list payloads without schema enforcement

**Example:**
```python
from spec_compiler import CompileRequest

request = CompileRequest(
    plan_id="plan-abc123",
    spec_index=0,
    spec_data={"type": "feature", "description": "Add authentication"},
    github_owner="my-org",
    github_repo="my-project"
)
```

#### CompileResponse

The response model for the compile endpoint:

```python
{
    "request_id": str,              # Unique UUID request identifier
    "plan_id": str,                 # Plan identifier (echoed from request)
    "spec_index": int,              # Spec index (echoed from request)
    "status": "accepted" | "failed", # Processing status
    "message": str | None           # Optional status message
}
```

**Status Values:**
- `accepted`: Request was accepted for processing
- `failed`: Request validation or processing failed

**Example:**
```python
from spec_compiler import CompileResponse

response = CompileResponse(
    request_id="550e8400-e29b-41d4-a716-446655440000",
    plan_id="plan-abc123",
    spec_index=0,
    status="accepted",
    message="Request accepted for processing"
)
```

### Using the Compile Endpoint

The compile endpoint accepts specification compilation requests and returns a 202 Accepted response while stubbing downstream LLM processing.

#### Making a Request

**Request:**
```bash
curl -X POST http://localhost:8080/compile-spec \
  -H "Content-Type: application/json" \
  -H "X-Request-Id: 550e8400-e29b-41d4-a716-446655440000" \
  -H "Idempotency-Key: my-unique-key-123" \
  -d '{
    "plan_id": "plan-abc123",
    "spec_index": 0,
    "spec_data": {
      "type": "feature",
      "description": "Add user authentication"
    },
    "github_owner": "my-org",
    "github_repo": "my-project"
  }'
```

**Response (HTTP 202 Accepted):**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "plan_id": "plan-abc123",
  "spec_index": 0,
  "status": "accepted",
  "message": "Request accepted for processing"
}
```

### Repository Context Integration

The compile endpoint automatically fetches repository context from GitHub to enhance LLM compilation. This includes the repository tree structure, dependencies, and file summaries.

#### How It Works

When a compile request is received, the service:

1. **Mints a GitHub Token**: Calls the configured GitHub token minting service to obtain a user-to-server access token for the target repository.
2. **Fetches Analysis Files**: Retrieves three JSON files from `.github/repo-analysis-output/` in the repository:
   - `tree.json`: Repository file tree structure
   - `dependencies.json`: Repository dependencies
   - `file-summaries.json`: Summaries of key repository files
3. **Builds Repo Context**: Assembles a `RepoContextPayload` containing the fetched data
4. **Fallback Handling**: If any file is missing (404) or malformed (invalid JSON), uses placeholder fallback data without failing the request
5. **Passes to LLM**: Includes the repo context in the metadata sent to downstream LLM services (currently stubbed)

#### Error Handling

**Token Minting Failures:**
- **500 Internal Server Error**: Minting service not configured (`MINTING_SERVICE_BASE_URL` missing)
- **502 Bad Gateway**: Minting service returned a 4xx error (client error)
- **503 Service Unavailable**: Minting service returned a 5xx error (temporary failure)

Error responses include structured JSON with `error`, `request_id`, `plan_id`, `spec_index`, and `message` fields.

**File Fetch Failures:**
- Missing files (404): Uses fallback placeholder data, logs warning, continues processing
- Malformed JSON: Uses fallback placeholder data, logs warning, continues processing
- GitHub API errors (403, 500, etc.): Uses fallback placeholder data, logs warning, continues processing
- Unexpected errors: Uses full fallback payload, logs error, continues processing

The compile endpoint is designed to be resilient—partial or complete failure to fetch repository context will not block the compilation request. Fallback data ensures downstream LLM processing can proceed with minimal context.

#### Fallback Data Structure

When analysis files are unavailable, the service uses these fallback structures:

**Tree Fallback:**
```json
[
  {
    "path": ".",
    "type": "tree",
    "mode": "040000",
    "sha": "unavailable",
    "url": "unavailable",
    "note": "Repository tree data unavailable"
  }
]
```

**Dependencies Fallback:**
```json
[
  {
    "name": "unknown",
    "version": "unknown",
    "ecosystem": "unknown",
    "note": "Dependency data unavailable"
  }
]
```

**File Summaries Fallback:**
```json
[
  {
    "path": "unknown",
    "summary": "File summary data unavailable",
    "lines": 0,
    "note": "Unable to fetch or summarize repository files"
  }
]
```

#### Structured Logging

The service logs detailed information about repo context fetching:

**Success Logs:**
- `minting_token_start`: Token minting initiated
- `minting_token_success`: Token successfully minted (includes token type, expiry info)
- `fetching_repo_context_start`: Repo context fetch initiated
- `repo_context_tree_success`: Tree file fetched successfully (includes entry count)
- `repo_context_dependencies_success`: Dependencies file fetched (includes dependency count)
- `repo_context_file_summaries_success`: File summaries fetched (includes summary count)
- `fetching_repo_context_success`: All files processed (includes counts for each type)

**Warning Logs (with fallback):**
- `repo_context_tree_error`: Tree file fetch failed (includes error, status code)
- `repo_context_tree_invalid_json`: Tree file has invalid JSON
- `repo_context_dependencies_error`: Dependencies file fetch failed
- `repo_context_dependencies_invalid_json`: Dependencies file has invalid JSON
- `repo_context_file_summaries_error`: File summaries fetch failed
- `repo_context_file_summaries_invalid_json`: File summaries has invalid JSON
- `repo_context_tree_not_list`: Tree data is not a list (using fallback)
- `repo_context_dependencies_not_list`: Dependencies data is not a list (using fallback)
- `repo_context_file_summaries_not_list`: File summaries data is not a list (using fallback)

**Error Logs:**
- `minting_token_failed`: Token minting failed (includes error, status code, context)
- `fetching_repo_context_unexpected_error`: Unexpected error during repo context fetch (uses full fallback)

All logs include `request_id`, `owner`, `repo` for correlation and debugging.

#### Configuration Requirements

To enable repository context fetching, configure:

```bash
# GitHub Token Minting Service
MINTING_SERVICE_BASE_URL=https://your-minting-service.run.app
MINTING_SERVICE_AUTH_HEADER=your-gcp-identity-token

# GitHub API (defaults to https://api.github.com)
GITHUB_API_BASE_URL=https://api.github.com
```

Without proper minting service configuration, compile requests will return a 500 error.


#### Request Headers

- **`X-Request-Id`** (optional): Client-provided request ID for distributed tracing. If not provided or invalid, a UUID will be generated.
- **`Idempotency-Key`** (optional): Client-provided idempotency key for request deduplication tracking. Currently logged but not used for actual deduplication.
- **`Content-Type`**: Must be `application/json`.
- **`Content-Length`**: Automatically set by HTTP clients. Requests exceeding `MAX_REQUEST_BODY_SIZE_BYTES` (default: 10MB) will be rejected with HTTP 413.

#### Response Codes

- **`202 Accepted`**: Request was validated and accepted for processing
- **`413 Request Entity Too Large`**: Request body exceeds size limit (configurable via `MAX_REQUEST_BODY_SIZE_BYTES`)
- **`422 Unprocessable Entity`**: Request validation failed (invalid fields, missing required data, etc.)
- **`500 Internal Server Error`**: Unexpected server error (logged with request_id for debugging)

#### Body Size Limits

Request body size is limited to prevent memory exhaustion. The limit is configurable via the `MAX_REQUEST_BODY_SIZE_BYTES` environment variable (default: 10MB).

```bash
# Configure in .env
MAX_REQUEST_BODY_SIZE_BYTES=10485760  # 10MB
```

Requests exceeding this limit will receive a 413 error:
```json
{
  "detail": "Request body exceeds maximum size limit of 10485760 bytes"
}
```

#### Validation Errors

Validation errors return HTTP 422 with detailed error information:

```json
{
  "detail": [
    {
      "loc": ["body", "plan_id"],
      "msg": "Field cannot be empty or whitespace-only",
      "type": "value_error"
    }
  ]
}
```

#### Edge Cases

- **`spec_index=0`**: Valid, as spec_index is zero-based
- **Empty `spec_data`**: Valid for both `{}` (dict) and `[]` (list)
- **Whitespace-only strings**: Rejected with validation error
- **Negative `spec_index`**: Rejected with validation error
- **Malformed JSON**: Rejected with HTTP 422
- **Missing required fields**: Rejected with HTTP 422 detailing all missing fields

#### Stubbed Behavior

**Current Implementation:**
- Accepts and validates requests
- Logs receipt with full context (plan_id, spec_index, github_owner/repo, request_id)
- Creates placeholder `LlmResponseEnvelope` with `{"status": "stubbed", "details": "LLM call not yet implemented"}`
- Logs the stubbed envelope as if dispatching to downstream service
- Returns HTTP 202 with tracking information

**Not Yet Implemented:**
- Actual GitHub API integration
- Real LLM API calls (OpenAI, Claude)
- Pub/Sub message publishing
- Request persistence or deduplication


### LLM Envelope Models (Skeletal)

These models are defined for future LLM integration and are currently used for typing and structural placeholders.

#### SystemPromptConfig

Configuration for system prompts:
```python
{
    "template": str,        # System prompt template
    "variables": dict,      # Variables for interpolation
    "max_tokens": int       # Maximum tokens (> 0)
}
```

#### RepoContextPayload

Repository context for LLM requests:
```python
{
    "tree": list[dict],           # Repository file tree structure
    "dependencies": list[dict],   # Repository dependencies
    "file_summaries": list[dict]  # File summaries for context
}
```

#### LlmRequestEnvelope

Envelope for LLM API requests:
```python
{
    "request_id": str,              # Unique request identifier
    "model": str,                   # LLM model (default: "gpt-5.1")
    "system_prompt": SystemPromptConfig,
    "user_prompt": str,
    "repo_context": RepoContextPayload | None,
    "metadata": dict
}
```

#### LlmResponseEnvelope

Envelope for LLM API responses:
```python
{
    "request_id": str,         # Request identifier for correlation
    "status": str,             # Response status
    "content": str,            # Response content from LLM
    "model": str | None,       # Model that generated response
    "usage": dict | None,      # Token usage information
    "metadata": dict           # Additional metadata
}
```

### Helper Functions

```python
from spec_compiler import generate_request_id, create_llm_response_stub

# Generate a unique UUID request ID
request_id = generate_request_id()

# Create a placeholder LLM response for testing/typing
stub = create_llm_response_stub(
    request_id=request_id,
    status="pending",
    content=""
)
```

## Maintainer Notes

### LLM Integration Placeholders

The compile endpoint currently uses **placeholder/stub LLM envelopes** to simulate the future workflow without making actual LLM API calls. This is intentional to allow the service infrastructure to be deployed and tested before integrating external LLM services.

**Current Behavior:**
- When a compile request is received, the endpoint creates an `LlmResponseEnvelope` with status `"pending"` and metadata `{"status": "stubbed", "details": "LLM call not yet implemented"}`
- This envelope is logged as if it were being dispatched to a downstream service
- The envelope is **not returned to the client** - clients only receive the `CompileResponse` with status `"accepted"`
- All LLM envelope models (`LlmRequestEnvelope`, `LlmResponseEnvelope`, `SystemPromptConfig`, `RepoContextPayload`) are defined but not actively used

**Log Destination and Access:**
- LLM envelope logs are written to **stdout in JSON format** (when `LOG_JSON=true`)
- In local development: View logs in your terminal or pipe through `jq` for readability
- In Docker: Use `docker logs -f <container-name>` to follow logs
- In Cloud Run: Logs are automatically indexed in **Google Cloud Logging**
  - Access via Cloud Console: Logging > Logs Explorer
  - Filter by `resource.type=cloud_run_revision` and `resource.labels.service_name=spec-compiler`
  - Search for `"Generated stubbed LLM response envelope"` to find envelope logs
- All logs include the `request_id` field for correlation and tracing through the request lifecycle

**Future Implementation:**
When integrating actual LLM services, the workflow should:
1. Create a real `LlmRequestEnvelope` with the specification context
2. Dispatch the request to the appropriate LLM service (OpenAI GPT-5.1, Claude Sonnet 4.5, or Gemini 3.0 Pro)
3. Handle async responses via Pub/Sub or webhooks
4. Update the compile status from `"accepted"` to `"failed"` or complete via async status endpoint
5. Implement request persistence and idempotency enforcement (currently only logs the key)

**Important Assumptions:**
- LLM API calls will be made according to the guidelines in `LLMs.md` (GPT-5.1 Responses API, Claude Messages API, Gemini API)
- API keys are loaded from environment variables (`OPENAI_API_KEY`, `CLAUDE_API_KEY`)
- The service is designed to be stateless - status updates would come via external Pub/Sub topics
- Request/response envelopes provide a consistent structure regardless of which LLM is called

**Testing Considerations:**
- The stubbed envelopes allow testing of the API contract without LLM dependencies
- Tests verify that envelopes are created and logged correctly
- When LLM integration is added, existing tests should be updated to mock LLM API calls rather than relying on stubs

## Structured Logging & Observability

This service uses **structured logging** with JSON output, designed for integration with Google Cloud Logging and other log aggregation systems.

### Logging Behavior

- **JSON Format**: When `LOG_JSON=true` (default), all logs are output as JSON with structured fields including `timestamp`, `level`, `logger`, `message`, and contextual data.
- **Request Tracing**: Every request receives a unique request ID (via `X-Request-Id` header) that's included in all logs for that request. This enables distributed tracing across services.
- **Error Handling**: Unhandled exceptions are caught by middleware, logged with full stack traces, and returned as structured JSON responses with format: `{ "error": "internal_error", "request_id": <uuid>, "message": <safe_summary> }`. This ensures consistent error responses and prevents leaking sensitive error details to clients.
- **Idempotency Support**: Optional `Idempotency-Key` header is logged and echoed in responses for client-side idempotency tracking (sanitized for safety).
- **Log Levels**: Controlled via `LOG_LEVEL` environment variable. Use `DEBUG` for development, `INFO` for production.
- **Google Cloud Logging**: When deployed to Cloud Run, structured JSON logs are automatically parsed and indexed by Google Cloud Logging, enabling powerful querying and alerting.

### Viewing Logs

**Local Development**:
```bash
# Human-readable logs (LOG_JSON=false)
LOG_JSON=false PYTHONPATH=src python -m uvicorn spec_compiler.app.main:app --host 0.0.0.0 --port 8080

# Structured JSON logs (LOG_JSON=true) - pipe through jq for readability (optional: install jq with your package manager)
LOG_JSON=true PYTHONPATH=src python -m uvicorn spec_compiler.app.main:app --host 0.0.0.0 --port 8080 | jq
```

**Docker Logs**:
```bash
# Follow container logs
docker logs -f spec-compiler-container

# With Makefile
make logs
```

**Cloud Run** (requires GCP access):
```bash
# View logs in Google Cloud Console
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=spec-compiler" --limit 50

# Or use the Cloud Console: Logging > Logs Explorer
```

### Log Correlation

All requests are automatically tagged with:
- `request_id`: Unique identifier for each request
- `path`: HTTP path
- `method`: HTTP method
- `status_code`: Response status
- `duration_ms`: Request duration in milliseconds

Use the request ID to trace a request through all log entries.

## Project Structure

```
spec-compiler/
├── src/
│   └── spec_compiler/
│       ├── __init__.py
│       ├── config.py              # Configuration management
│       ├── logging.py             # Structured logging setup
│       ├── models/                # API models and types
│       │   ├── __init__.py        # Model exports and helpers
│       │   ├── compile.py         # CompileRequest/Response models
│       │   └── llm.py             # LLM envelope models
│       ├── middleware/
│       │   ├── __init__.py
│       │   ├── error_handler.py    # Error handling middleware
│       │   └── request_id.py       # Request ID middleware
│       └── app/
│           ├── __init__.py
│           ├── main.py            # FastAPI application
│           └── routes/
│               ├── __init__.py
│               └── health.py      # Health check routes
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── test_health.py             # Health endpoint tests
│   ├── test_models_compile.py     # Compile models tests
│   ├── test_models_llm.py         # LLM models tests
│   └── test_models_helpers.py     # Model helpers tests
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Project configuration
├── .env.example                   # Environment variables template
├── LLMs.md                        # LLM integration guidelines
└── README.md                      # This file
```

## Docker Deployment

This service is fully containerized and designed for deployment on Google Cloud Run or any container orchestration platform.

### Building the Docker Image

Build the image using the provided Makefile:

```bash
make build
```

Or build directly with Docker:

```bash
docker build -t spec-compiler:latest .
```

The Dockerfile uses multi-stage builds for optimized layer caching and minimal image size. It:
- Uses `python:3.11-slim` base image
- Installs dependencies in a separate stage for better caching
- Runs as non-root user (`appuser`)
- Exposes port 8080 (configurable via `PORT` environment variable)
- Includes health check endpoint

### Running the Container Locally

#### Production Mode

Run with production settings:

```bash
make run
```

Or with Docker directly:

```bash
docker run -d \
  --name spec-compiler \
  -p 8080:8080 \
  -e PORT=8080 \
  -e APP_ENV=production \
  spec-compiler:latest
```

#### Development Mode

Run with development settings and environment variables from `.env`:

```bash
make run-dev
```

Or with custom port:

```bash
make run-dev PORT=3000
```

#### Interactive Mode (Debugging)

Run interactively to see logs in real-time:

```bash
make run-interactive
```

### Docker Commands

The Makefile provides convenient targets:

- `make build` - Build the Docker image
- `make run` - Run container in production mode
- `make run-dev` - Run container in development mode with `.env` file
- `make run-interactive` - Run container interactively (for debugging)
- `make logs` - Show container logs
- `make stop` - Stop and remove the container
- `make clean` - Stop container and remove image
- `make help` - Show all available commands

### Environment Variables for Docker

When running in a container, you can configure the service using environment variables:

- `PORT` - Port to bind to (default: 8080, Cloud Run will set this automatically)
- `APP_ENV` - Application environment (development, staging, production)
- `LOG_JSON` - Enable JSON logging (default: true, **required** for Cloud Run integration with Google Cloud Logging)
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `OPENAI_API_KEY` - OpenAI API key (optional, not yet used)
- `CLAUDE_API_KEY` - Anthropic API key (optional, not yet used)
- `GCP_PROJECT_ID` - Google Cloud Project ID (optional, not yet used)
- `CORS_ORIGINS` - Comma-separated CORS origins

**Cloud Run Requirements**: When deploying to Cloud Run, ensure `LOG_JSON=true` to enable proper integration with Google Cloud Logging. Cloud Run expects JSON-formatted logs on stdout for indexing and querying. The application automatically handles this when `LOG_JSON=true`.

Example with environment variables:

```bash
docker run -d \
  --name spec-compiler \
  -p 8080:8080 \
  -e PORT=8080 \
  -e APP_ENV=production \
  -e LOG_JSON=true \
  -e LOG_LEVEL=INFO \
  -e OPENAI_API_KEY=sk-your-key \
  spec-compiler:latest
```

### Deploying to Google Cloud Run

The Makefile includes helper commands for Cloud Run deployment:

#### 1. Build and push to Google Container Registry:

```bash
make gcloud-build GCP_PROJECT_ID=your-project-id
```

#### 2. Deploy to Cloud Run:

```bash
make gcloud-deploy GCP_PROJECT_ID=your-project-id CLOUD_RUN_SERVICE=spec-compiler
```

Or deploy manually with `gcloud`:

```bash
# Build and push
gcloud builds submit --tag gcr.io/your-project-id/spec-compiler

# Deploy to Cloud Run
gcloud run deploy spec-compiler \
  --image gcr.io/your-project-id/spec-compiler:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --port 8080 \
  --memory 512Mi \
  --cpu 1 \
  --max-instances 10 \
  --set-env-vars APP_ENV=production,LOG_JSON=true
```

### Container Features

- **Non-root user**: Runs as `appuser` (UID 1000) for security
- **Multi-stage build**: Optimized layers for faster builds and smaller images
- **Health check**: Built-in Docker health check on `/health` endpoint
- **Graceful shutdown**: Properly handles SIGTERM for clean shutdowns
- **Structured logging**: JSON logs to stdout (compatible with Cloud Logging)
- **Request tracing**: Automatic request ID generation and propagation
- **Configurable port**: Respects `PORT` environment variable (Cloud Run compatible)

Template README to persist license, contribution rules, and author throughout agent foundry projects. This sentence and the main title can be changed but permanents and below should be left alone.



# Permanents (License, Contributing, Author)

Do not change any of the below sections

## License

This Agent Foundry Project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## Contributing

Feel free to submit issues and enhancement requests!

## Author

Created by Agent Foundry and John Brosnihan
