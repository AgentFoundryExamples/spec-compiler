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

### Running the Service

Start the development server:
```bash
PYTHONPATH=src python -m uvicorn spec_compiler.app.main:app --host 0.0.0.0 --port 8080 --reload
```

The service will be available at:
- API: http://localhost:8080
- Interactive API docs (Swagger UI): http://localhost:8080/docs
- OpenAPI schema: http://localhost:8080/openapi.json

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

## Configuration

All configuration is managed through environment variables. See `.env.example` for all available options.

Key configuration variables:
- `APP_ENV`: Application environment (development, staging, production)
- `PORT`: Server port (default: 8080)
- `OPENAI_API_KEY`: OpenAI API key for GPT models
- `CLAUDE_API_KEY`: Anthropic API key for Claude models
- `GCP_PROJECT_ID`: Google Cloud Project ID
- `CORS_ORIGINS`: Comma-separated list of allowed CORS origins
- `LOG_LEVEL`: Logging level (default: INFO)
- `LOG_JSON`: Enable JSON logging (default: true)

## API Endpoints

- `GET /health`: Health check endpoint returning `{"status": "ok"}`
- `GET /version`: Version information with git SHA and environment
- `GET /docs`: Interactive API documentation (Swagger UI)
- `GET /openapi.json`: OpenAPI specification

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

## Deployment

This service is designed for deployment on Google Cloud Run but can run in any containerized environment.

### Docker (example)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
ENV PYTHONPATH=/app/src
CMD ["uvicorn", "spec_compiler.app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

Template README to persist license, contribution rules, and author throughout agent foundry projects. This sentence and the main title can be changed but permanents and below should be left alone.



# Permanents (License, Contributing, Author)

Do not change any of the below sections

## License

This Agent Foundry Project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## Contributing

Feel free to submit issues and enhancement requests!

## Author

Created by Agent Foundry and John Brosnihan
