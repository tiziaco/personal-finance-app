install:
	pip install uv
	uv sync

DOCKER_COMPOSE ?= docker-compose

set-env:
	@if [ -z "$(ENV)" ]; then \
		echo "ENV is not set. Usage: make set-env ENV=development|staging|production"; \
		exit 1; \
	fi
	@if [ "$(ENV)" != "development" ] && [ "$(ENV)" != "staging" ] && [ "$(ENV)" != "production" ] && [ "$(ENV)" != "test" ]; then \
		echo "ENV is not valid. Must be one of: development, staging, production, test"; \
		exit 1; \
	fi
	@echo "Setting environment to $(ENV)"
	@bash -c "source scripts/set_env.sh $(ENV)"

prod:
	@echo "Starting server in production environment"
	@bash -c "source scripts/set_env.sh production && ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop uvloop"

staging:
	@echo "Starting server in staging environment"
	@bash -c "source scripts/set_env.sh staging && ./.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --loop uvloop"

dev:
	@echo "Starting server in development environment"
	@bash -c "source scripts/set_env.sh development && uv run uvicorn app.main:app --reload --host localhost --port 8000 --loop uvloop"

# Evaluation commands
eval:
	@echo "Running evaluation with interactive mode"
	@bash -c "source scripts/set_env.sh ${ENV:-development} && python -m evals.main --interactive"

eval-quick:
	@echo "Running evaluation with default settings"
	@bash -c "source scripts/set_env.sh ${ENV:-development} && python -m evals.main --quick"

eval-no-report:
	@echo "Running evaluation without generating report"
	@bash -c "source scripts/set_env.sh ${ENV:-development} && python -m evals.main --no-report"

# Testing commands
# APP_ENV=test is enough — pydantic-settings auto-loads .env.test
test:
	@echo "Running all tests"
	@APP_ENV=test uv run pytest tests/ -v

test-unit:
	@echo "Running unit tests"
	@APP_ENV=test uv run pytest tests/unit/ -v -m unit

test-integration:
	@echo "Running integration tests"
	@APP_ENV=test uv run pytest tests/integration/ -v -m integration

test-coverage:
	@echo "Running all tests with coverage report"
	@APP_ENV=test uv run pytest tests/ -v \
		--cov=app \
		--cov-report=term-missing \
		--cov-report=html:htmlcov \
		--cov-report=xml:coverage.xml

test-fast:
	@echo "Running all tests except slow ones"
	@APP_ENV=test uv run pytest tests/ -v -m "not slow"

lint:
	ruff check .

format:
	ruff format .

clean:
	rm -rf .venv
	rm -rf __pycache__
	rm -rf .pytest_cache

docker-build:
	@if [ -f .env.development ]; then \
		source .env.development && \
		DOCKER_IMAGE=$$(echo "$$PROJECT_NAME" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | sed 's/^-//' | sed 's/-$$//') && \
		docker build -t "$$DOCKER_IMAGE" .; \
	else \
		echo ".env.development not found"; \
		exit 1; \
	fi

docker-build-env:
	@if [ -z "$(ENV)" ]; then \
		echo "ENV is not set. Usage: make docker-build-env ENV=development|staging|production"; \
		exit 1; \
	fi
	@if [ "$(ENV)" != "development" ] && [ "$(ENV)" != "staging" ] && [ "$(ENV)" != "production" ]; then \
		echo "ENV is not valid. Must be one of: development, staging, production"; \
		exit 1; \
	fi
	@./scripts/build-docker.sh $(ENV)

docker-run:
	@ENV_FILE=.env.development; \
	if [ ! -f $$ENV_FILE ]; then \
		echo "Environment file $$ENV_FILE not found. Please create it."; \
		exit 1; \
	fi; \
	APP_ENV=development $(DOCKER_COMPOSE) --env-file $$ENV_FILE up -d --build db app

docker-run-env:
	@if [ -z "$(ENV)" ]; then \
		echo "ENV is not set. Usage: make docker-run-env ENV=development|staging|production"; \
		exit 1; \
	fi
	@if [ "$(ENV)" != "development" ] && [ "$(ENV)" != "staging" ] && [ "$(ENV)" != "production" ]; then \
		echo "ENV is not valid. Must be one of: development, staging, production"; \
		exit 1; \
	fi
	@ENV_FILE=.env.$(ENV); \
	if [ ! -f $$ENV_FILE ]; then \
		echo "Environment file $$ENV_FILE not found. Please create it."; \
		exit 1; \
	fi; \
	APP_ENV=$(ENV) $(DOCKER_COMPOSE) --env-file $$ENV_FILE up -d --build db app
	# @./scripts/ensure-db-user.sh $(ENV)

docker-logs:
	@if [ -z "$(ENV)" ]; then \
		echo "ENV is not set. Usage: make docker-logs ENV=development|staging|production"; \
		exit 1; \
	fi
	@if [ "$(ENV)" != "development" ] && [ "$(ENV)" != "staging" ] && [ "$(ENV)" != "production" ]; then \
		echo "ENV is not valid. Must be one of: development, staging, production"; \
		exit 1; \
	fi
	@ENV_FILE=.env.$(ENV); \
	if [ ! -f $$ENV_FILE ]; then \
		echo "Environment file $$ENV_FILE not found. Please create it."; \
		exit 1; \
	fi; \
	APP_ENV=$(ENV) $(DOCKER_COMPOSE) --env-file $$ENV_FILE logs -f app db

docker-stop:
	@if [ -z "$(ENV)" ]; then \
		echo "ENV is not set. Usage: make docker-stop ENV=development|staging|production"; \
		exit 1; \
	fi
	@if [ "$(ENV)" != "development" ] && [ "$(ENV)" != "staging" ] && [ "$(ENV)" != "production" ]; then \
		echo "ENV is not valid. Must be one of: development, staging, production"; \
		exit 1; \
	fi
	@ENV_FILE=.env.$(ENV); \
	if [ ! -f $$ENV_FILE ]; then \
		echo "Environment file $$ENV_FILE not found. Please create it."; \
		exit 1; \
	fi; \
	APP_ENV=$(ENV) $(DOCKER_COMPOSE) --env-file $$ENV_FILE down

docker-run-db:
	@if [ -z "$(ENV)" ]; then \
		echo "ENV is not set. Usage: make docker-run-db ENV=development|staging|production"; \
		exit 1; \
	fi
	@if [ "$(ENV)" != "development" ] && [ "$(ENV)" != "staging" ] && [ "$(ENV)" != "production" ]; then \
		echo "ENV is not valid. Must be one of: development, staging, production"; \
		exit 1; \
	fi
	@ENV_FILE=.env.$(ENV); \
	if [ ! -f $$ENV_FILE ]; then \
		echo "Environment file $$ENV_FILE not found. Please create it."; \
		exit 1; \
	fi; \
	APP_ENV=$(ENV) $(DOCKER_COMPOSE) --env-file $$ENV_FILE up -d db

# Migrations
migrate:
	@if [ -z "$(ENV)" ]; then \
		echo "Error: ENV is required. Usage: make migrate ENV=<environment>"; \
		exit 1; \
	fi; \
	ENV_FILE=.env.$(ENV); \
	if [ ! -f $$ENV_FILE ]; then \
		echo "Error: Environment file $$ENV_FILE not found"; \
		exit 1; \
	fi; \
	echo "Running migrations for $(ENV) environment..."; \
	set -a && . ./$$ENV_FILE && set +a && \
	APP_ENV=$(ENV) uv run alembic upgrade head

migrate-create:
	@if [ -z "$(ENV)" ]; then \
		echo "Error: ENV is required. Usage: make migrate-create ENV=<environment> MSG='migration message'"; \
		exit 1; \
	fi; \
	if [ -z "$(MSG)" ]; then \
		echo "Error: MSG is required. Usage: make migrate-create ENV=<environment> MSG='migration message'"; \
		exit 1; \
	fi; \
	ENV_FILE=.env.$(ENV); \
	if [ ! -f $$ENV_FILE ]; then \
		echo "Error: Environment file $$ENV_FILE not found"; \
		exit 1; \
	fi; \
	echo "Creating migration for $(ENV) environment..."; \
	set -a && . ./$$ENV_FILE && set +a && \
	APP_ENV=$(ENV) uv run alembic revision --autogenerate -m "$(MSG)"

migrate-downgrade:
	@if [ -z "$(ENV)" ]; then \
		echo "Error: ENV is required. Usage: make migrate-downgrade ENV=<environment> [REV=-1]"; \
		exit 1; \
	fi; \
	ENV_FILE=.env.$(ENV); \
	if [ ! -f $$ENV_FILE ]; then \
		echo "Error: Environment file $$ENV_FILE not found"; \
		exit 1; \
	fi; \
	REV=$${REV:--1}; \
	echo "Downgrading migrations for $(ENV) environment to $$REV..."; \
	set -a && . ./$$ENV_FILE && set +a && \
	APP_ENV=$(ENV) uv run alembic downgrade $$REV

migrate-history:
	@if [ -z "$(ENV)" ]; then \
		echo "Error: ENV is required. Usage: make migrate-history ENV=<environment>"; \
		exit 1; \
	fi; \
	ENV_FILE=.env.$(ENV); \
	if [ ! -f $$ENV_FILE ]; then \
		echo "Error: Environment file $$ENV_FILE not found"; \
		exit 1; \
	fi; \
	echo "Migration history for $(ENV) environment:"; \
	set -a && . ./$$ENV_FILE && set +a && \
	APP_ENV=$(ENV) uv run alembic history --verbose

migrate-current:
	@if [ -z "$(ENV)" ]; then \
		echo "Error: ENV is required. Usage: make migrate-current ENV=<environment>"; \
		exit 1; \
	fi; \
	ENV_FILE=.env.$(ENV); \
	if [ ! -f $$ENV_FILE ]; then \
		echo "Error: Environment file $$ENV_FILE not found"; \
		exit 1; \
	fi; \
	echo "Current migration for $(ENV) environment:"; \
	set -a && . ./$$ENV_FILE && set +a && \
	APP_ENV=$(ENV) uv run alembic current

# Help
help:
	@echo "Usage: make <target>"
	@echo "Targets:"
	@echo "  install: Install dependencies"
	@echo "  set-env ENV=<environment>: Set environment variables (development, staging, production, test)"
	@echo "  run ENV=<environment>: Set environment and run server"
	@echo "  prod: Run server in production environment"
	@echo "  staging: Run server in staging environment"
	@echo "  dev: Run server in development environment"
	@echo "  eval: Run evaluation with interactive mode"
	@echo "  eval-quick: Run evaluation with default settings"
	@echo "  eval-no-report: Run evaluation without generating report"
	@echo "  test: Run all tests"
	@echo "  test-unit: Run unit tests only"
	@echo "  test-integration: Run integration tests only"
	@echo "  test-coverage: Run all tests with HTML + XML coverage report"
	@echo "  test-fast: Run all tests except slow ones"
	@echo "  clean: Clean up"
	@echo "  docker-build: Build default Docker image"
	@echo "  docker-build-env ENV=<environment>: Build Docker image for specific environment"
	@echo "  docker-run: Run default Docker container"
	@echo "  docker-run-env ENV=<environment>: Run Docker container for specific environment"
	@echo "  docker-logs ENV=<environment>: View logs from running container"
	@echo "  docker-stop ENV=<environment>: Stop and remove container"
	@echo "  migrate ENV=<environment>: Run database migrations"
	@echo "  migrate-create ENV=<environment> MSG='message': Create new migration"
	@echo "  migrate-downgrade ENV=<environment> [REV=-1]: Downgrade migrations"
	@echo "  migrate-history ENV=<environment>: Show migration history"
	@echo "  migrate-current ENV=<environment>: Show current migration version"