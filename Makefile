.PHONY: help docker-build docker-build-web docker-build-api docker-run docker-run-core docker-run-db docker-stop docker-logs docker-logs-core clean rebuild rebuild-core

DOCKER_COMPOSE ?= docker-compose
ENV ?= development

# Load root .env (APP_ENV, GRAFANA_ADMIN_PASSWORD, …) so Docker Compose picks
# them up even when --env-file points to a service-specific file.
include .env
.EXPORT_ALL_VARIABLES:

# Default target
help:
	@echo "Build Commands:"
	@echo "  make docker-build       - Build all services (web-app, server)"
	@echo "  make docker-build-web   - Build web-app service only"
	@echo "  make docker-build-api   - Build server service only"
	@echo ""
	@echo "Up/Down Commands:"
	@echo "  make docker-run         - Start full stack (web-app, server, db, prometheus, grafana, cadvisor)"
	@echo "  make docker-run-core    - Start core services only (web-app, server, db)"
	@echo "  make docker-run-db      - Start database only (requires ENV)"
	@echo "  make docker-stop        - Stop all services"
	@echo ""
	@echo "Logs & Utils:"
	@echo "  make docker-logs        - Follow logs for all services"
	@echo "  make docker-logs-core   - Follow logs for core services"
	@echo "  make rebuild            - Clean, build, and start full stack"
	@echo "  make rebuild-core       - Clean, build, and start core stack"
	@echo "  make clean              - Stop and remove all services, volumes, networks"
	@echo ""
	@echo "Environment:"
	@echo "  ENV=development (default) | staging | production"

# Build commands
docker-build:
	@echo "🔨 Building all services..."
	@$(DOCKER_COMPOSE) build web-app server
	@echo "✅ All services built"

docker-build-web:
	@echo "🔨 Building web-app service..."
	@$(DOCKER_COMPOSE) build web-app
	@echo "✅ web-app built"

docker-build-api:
	@echo "🔨 Building server service..."
	@$(DOCKER_COMPOSE) build server
	@echo "✅ server built"

# Full stack - all services including monitoring
docker-run:
	@echo "🚀 Starting full stack (development mode)"
	@echo "Services: web-app, server, db, prometheus, grafana, cadvisor"
	@$(DOCKER_COMPOSE) up -d
	@echo ""
	@echo "✅ Full stack is running!"
	@echo "   Web App:     http://localhost:3000"
	@echo "   Server:      http://localhost:8000"
	@echo "   Prometheus:  http://localhost:9090"
	@echo "   Grafana:     http://localhost:3001 (admin/admin)"
	@echo "   cAdvisor:    http://localhost:8080"
	@echo "   Database:    localhost:5432"

# Core stack - essential services only (no monitoring)
docker-run-core:
	@echo "🚀 Starting core stack (essential services only)"
	@echo "Services: web-app, server, db"
	@$(DOCKER_COMPOSE) up -d web-app server db
	@echo ""
	@echo "✅ Core stack is running!"
	@echo "   Web App:     http://localhost:3000"
	@echo "   Server:      http://localhost:8000"
	@echo "   Database:    localhost:5432"

# Database only - for local development
docker-run-db:
	@if [ -z "$(ENV)" ]; then \
		echo "ENV is not set. Usage: make docker-run-db ENV=development|staging|production"; \
		exit 1; \
	fi
	@if [ "$(ENV)" != "development" ] && [ "$(ENV)" != "staging" ] && [ "$(ENV)" != "production" ]; then \
		echo "ENV is not valid. Must be one of: development, staging, production"; \
		exit 1; \
	fi
	@ENV_FILE=server/.env.$(ENV); \
	if [ ! -f $$ENV_FILE ]; then \
		echo "Environment file $$ENV_FILE not found. Please create it."; \
		exit 1; \
	fi; \
	APP_ENV=$(ENV) $(DOCKER_COMPOSE) --env-file $$ENV_FILE up -d db
	@echo ""
	@echo "✅ Database is running!"
	@echo "   Database:    localhost:5432"

# Stop all services
docker-stop:
	@echo "📛 Stopping all services..."
	@$(DOCKER_COMPOSE) down
	@echo "✅ All services stopped"

# View logs
docker-logs:
	@echo "📋 Following logs for all services..."
	@$(DOCKER_COMPOSE) logs -f

docker-logs-core:
	@echo "📋 Following logs for core stack..."
	@$(DOCKER_COMPOSE) logs -f web-app server db

# Clean up everything
clean:
	@echo "🧹 Cleaning up all services, volumes, and networks..."
	@$(DOCKER_COMPOSE) down -v
	@echo "✅ Cleanup complete"

# Rebuild and start fresh
rebuild: clean docker-run

rebuild-core: clean docker-run-core
