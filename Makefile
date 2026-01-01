.PHONY: help build run run-dev stop clean test lint format

# Default values
IMAGE_NAME ?= spec-compiler
IMAGE_TAG ?= latest
CONTAINER_NAME ?= spec-compiler-container
PORT ?= 8080
APP_ENV ?= development

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-15s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

build: ## Build Docker image
	@echo "Building Docker image $(IMAGE_NAME):$(IMAGE_TAG)..."
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) .
	@echo "Build complete!"

run: ## Run container in production mode
	@echo "Starting container $(CONTAINER_NAME) on port $(PORT)..."
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT):8080 \
		-e PORT=8080 \
		-e APP_ENV=production \
		-e LOG_JSON=true \
		-e LOG_LEVEL=INFO \
		$(IMAGE_NAME):$(IMAGE_TAG)
	@echo "Container started! Access at http://localhost:$(PORT)"
	@echo "Health check: http://localhost:$(PORT)/health"
	@echo "API docs: http://localhost:$(PORT)/docs"

run-dev: ## Run container in development mode with environment variables
	@echo "Starting container $(CONTAINER_NAME) in development mode on port $(PORT)..."
	docker run -d \
		--name $(CONTAINER_NAME) \
		-p $(PORT):8080 \
		-e PORT=8080 \
		-e APP_ENV=$(APP_ENV) \
		-e LOG_JSON=false \
		-e LOG_LEVEL=DEBUG \
		--env-file .env \
		$(IMAGE_NAME):$(IMAGE_TAG)
	@echo "Container started! Access at http://localhost:$(PORT)"
	@echo "Health check: http://localhost:$(PORT)/health"
	@echo "API docs: http://localhost:$(PORT)/docs"

run-interactive: ## Run container interactively (for debugging)
	@echo "Starting container in interactive mode..."
	docker run -it --rm \
		-p $(PORT):8080 \
		-e PORT=8080 \
		-e APP_ENV=$(APP_ENV) \
		-e LOG_JSON=false \
		$(IMAGE_NAME):$(IMAGE_TAG)

logs: ## Show container logs
	docker logs -f $(CONTAINER_NAME)

stop: ## Stop running container
	@echo "Stopping container $(CONTAINER_NAME)..."
	-docker stop $(CONTAINER_NAME)
	-docker rm $(CONTAINER_NAME)
	@echo "Container stopped and removed."

clean: stop ## Stop container and remove image
	@echo "Removing image $(IMAGE_NAME):$(IMAGE_TAG)..."
	-docker rmi $(IMAGE_NAME):$(IMAGE_TAG)
	@echo "Cleanup complete."

test: ## Run tests locally (requires Python environment)
	@echo "Running tests..."
	PYTHONPATH=src pytest tests/ -v

lint: ## Run linters locally (requires Python environment)
	@echo "Running linters..."
	ruff check src/ tests/
	mypy src/

format: ## Format code locally (requires Python environment)
	@echo "Formatting code..."
	black src/ tests/
	ruff check --fix src/ tests/

# Docker Compose targets (if docker-compose.yml is added in the future)
# These are placeholders for future multi-service orchestration
compose-up: ## Start services with docker-compose
	docker-compose up -d

compose-down: ## Stop services with docker-compose
	docker-compose down

compose-logs: ## Show docker-compose logs
	docker-compose logs -f

# Cloud Run deployment helpers
gcloud-build: ## Build and push to Google Container Registry
	@echo "Building and pushing to GCR..."
	@if [ -z "$(GCP_PROJECT_ID)" ]; then \
		echo "Error: GCP_PROJECT_ID is not set"; \
		exit 1; \
	fi
	gcloud builds submit --tag gcr.io/$(GCP_PROJECT_ID)/$(IMAGE_NAME):$(IMAGE_TAG)

gcloud-deploy: ## Deploy to Cloud Run
	@echo "Deploying to Cloud Run..."
	@if [ -z "$(GCP_PROJECT_ID)" ]; then \
		echo "Error: GCP_PROJECT_ID is not set"; \
		exit 1; \
	fi
	@if [ -z "$(CLOUD_RUN_SERVICE)" ]; then \
		echo "Error: CLOUD_RUN_SERVICE is not set"; \
		exit 1; \
	fi
	gcloud run deploy $(CLOUD_RUN_SERVICE) \
		--image gcr.io/$(GCP_PROJECT_ID)/$(IMAGE_NAME):$(IMAGE_TAG) \
		--platform managed \
		--region us-central1 \
		--allow-unauthenticated \
		--port 8080 \
		--memory 512Mi \
		--cpu 1 \
		--max-instances 10 \
		--set-env-vars APP_ENV=production,LOG_JSON=true
