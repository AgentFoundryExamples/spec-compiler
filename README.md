# Spec Compiler Service

A FastAPI service for compiling specifications with LLM integrations. This service provides a robust foundation with health checks, structured logging, request tracing, and observability features designed for Cloud Run deployment.

## Features

- **FastAPI Framework**: Modern async Python web framework with automatic OpenAPI documentation
- **Structured Logging**: JSON-formatted logs compatible with Google Cloud Logging
- **Request Tracing**: Automatic request ID propagation for distributed tracing
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

#### Request Tracing
- **`REQUEST_ID_HEADER`**: HTTP header name for request correlation (default: `X-Request-Id`). Used for distributed tracing.

**⚠️ Important Notes**:
- GitHub integration, LLM API calls, and Pub/Sub messaging are **not yet implemented**. The corresponding environment variables are placeholders for future features.
- Never commit real API keys, tokens, or secrets to version control. Always use `.env` for local secrets (already in `.gitignore`).
- For production deployments, use your platform's secret management system (e.g., Google Cloud Secret Manager, AWS Secrets Manager).

## API Endpoints

### Health & Monitoring
- **`GET /health`**: Health check endpoint returning `{"status": "ok"}`. Used by Cloud Run and Docker health checks.
- **`GET /version`**: Version information including app version, git SHA (if available), and environment.

### Documentation
- **`GET /docs`**: Interactive API documentation (Swagger UI). Automatically generated from OpenAPI schema.
- **`GET /openapi.json`**: OpenAPI specification in JSON format. Use this for code generation or API clients.

## Structured Logging & Observability

This service uses **structured logging** with JSON output, designed for integration with Google Cloud Logging and other log aggregation systems.

### Logging Behavior

- **JSON Format**: When `LOG_JSON=true` (default), all logs are output as JSON with structured fields including `timestamp`, `level`, `logger`, `message`, and contextual data.
- **Request Tracing**: Every request receives a unique request ID (via `X-Request-Id` header) that's included in all logs for that request. This enables distributed tracing across services.
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
│       ├── middleware/
│       │   ├── __init__.py
│       │   └── request_id.py      # Request ID middleware
│       └── app/
│           ├── __init__.py
│           ├── main.py            # FastAPI application
│           └── routes/
│               ├── __init__.py
│               └── health.py      # Health check routes
├── tests/
│   ├── __init__.py
│   ├── conftest.py               # Pytest fixtures
│   └── test_health.py            # Health endpoint tests
├── requirements.txt              # Python dependencies
├── pyproject.toml               # Project configuration
├── .env.example                 # Environment variables template
└── README.md                    # This file
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
