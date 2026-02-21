# Personal Finance App

A personal finance application powered by specialized AI agents that helps you manage, categorize, and understand your financial transactions. The app uses advanced language models to automatically label and analyze your data, surfacing clear insights into spending patterns, recurring subscriptions, trends, anomalies, and overall financial behavior for dashboard or notebook workflows.

## 🌟 Key Features

- **AI-Powered Analysis**: Specialized agents automatically categorize and analyze transactions
- **Next.js Frontend**: Modern, responsive web interface
- **FastAPI Backend**: High-performance async API with LangGraph AI agents
- **Clerk Authentication**: Secure user authentication and management
- **PostgreSQL Database**: Reliable data persistence with vector support
- **Monitoring & Observability**: Prometheus metrics and Grafana dashboards
- **GDPR Compliant**: Full right-to-erasure support and data privacy

## 📋 Prerequisites

- **Docker & Docker Compose** (recommended for quick setup)
- OR
- **Python 3.11+** (for local backend development)
- **Node.js 18+** & **npm** (for local frontend development)
- **PostgreSQL 14+** (if running database separately)

## 🚀 Quick Start

### Option 1: Docker (Recommended)

The easiest way to get the entire application running:

```bash
# Start the full stack (web-app, server, database, monitoring)
make docker-run

# Or start just the core services (no monitoring)
make docker-run-core
```

**Access the services:**
- **Web App**: http://localhost:3000
- **API Server**: http://localhost:8000
- **Grafana**: http://localhost:3001 (admin/admin)
- **Prometheus**: http://localhost:9090

To stop all services:

```bash
make docker-stop
```

### Option 2: Local Development Setup

#### Backend (Server)

```bash
cd server

# Install dependencies using uv
make install

# Set environment to development
make set-env ENV=development

# Start the development server (with auto-reload)
make dev
```

The API will be available at `http://localhost:8000`. 

**API Documentation**: http://localhost:8000/docs (interactive Swagger UI)

#### Frontend (Web App)

```bash
cd web-app

# Install dependencies
npm install

# Start development server
npm run dev
```

The web app will be available at `http://localhost:3000`.

## 🔧 Common Commands

### Building

```bash
# Build all services (web-app and server)
make docker-build

# Build specific service
make docker-build-web    # Build web-app only
make docker-build-api    # Build server only
```

### Development

```bash
cd server

# Run the development server with hot-reload
make dev

# Run tests
make test                 # All tests
make test-unit           # Unit tests only
make test-integration    # Integration tests only
make test-coverage       # Tests with coverage report
make test-fast           # Exclude slow tests

# Linting and formatting
make lint                 # Check code style
make format              # Format code

# Evaluation
make eval                # Run evaluation suite
make eval-quick          # Quick evaluation
```

### Monitoring & Debugging

```bash
# View Docker logs
make docker-logs         # All services
make docker-logs-core    # Core services only

# Rebuild and restart everything
make rebuild             # Full stack
make rebuild-core        # Core stack
```

## 📁 Project Structure

```
personal-finance-app/
├── server/               # FastAPI backend with AI agents
│   ├── app/             # Main application code
│   │   ├── agents/      # LangGraph AI agents
│   │   ├── api/         # API routes and endpoints
│   │   ├── core/        # Configuration, logging, metrics
│   │   ├── database/    # Database connections and models
│   │   ├── models/      # SQLAlchemy ORM models
│   │   ├── schemas/     # Pydantic schemas for validation
│   │   └── services/    # Business logic services
│   ├── tests/           # Test suite (unit & integration)
│   ├── evals/           # Model evaluation framework
│   ├── alembic/         # Database migrations
│   ├── Makefile         # Server commands
│   └── pyproject.toml   # Python dependencies
│
├── web-app/             # Next.js frontend
│   ├── src/
│   │   ├── app/         # Next.js app router pages
│   │   ├── components/  # React components
│   │   ├── hooks/       # Custom React hooks
│   │   ├── lib/         # Utilities and helpers
│   │   ├── types/       # TypeScript types
│   │   └── providers/   # Context providers
│   ├── public/          # Static assets
│   ├── Makefile         # Web-app commands
│   └── package.json     # Node dependencies
│
├── docker-compose.yml   # Multi-container setup
├── docker-compose.prod.yml  # Production setup
├── Makefile            # Root-level commands
└── README.md           # This file
```

## 🔐 Authentication & Security

The application uses **Clerk** for authentication. See [Authentication Documentation](server/docs/authentication.md) for detailed setup and configuration.

For security guidelines and best practices, refer to:
- [GDPR Compliance Guide](server/docs/gdpr-compliance-guide.md)

## 🧪 Testing

The project includes comprehensive test coverage:

```bash
cd server

# Run all tests with coverage
make test-coverage

# Tests are organized as:
# - tests/unit/         - Unit tests for individual components
# - tests/integration/  - Integration tests for API endpoints
```

Coverage reports are generated in `htmlcov/` directory.

## 📊 Monitoring

The application includes observability tools:

- **Prometheus**: Collects metrics from the application
- **Grafana**: Visualizes metrics and system performance
- **Langfuse**: LLM observability and trace analysis

Access Grafana dashboards at `http://localhost:3001` (credentials: admin/admin)

## 🌍 Environment Configuration

The application supports multiple environments:

```bash
# Development (default, with auto-reload and debug logging)
ENV=development make docker-run

# Staging
ENV=staging make docker-run

# Production
ENV=production make docker-run
```

Each environment has its own configuration file:
- `.env.development` - Development settings
- `.env.staging` - Staging settings
- `.env.production` - Production settings

See the respective README files for environment-specific setup:
- [Server Setup](server/README.md)
- [Web App Setup](web-app/README.md)

## 📚 Additional Documentation

- [Server Documentation](server/README.md) - Backend architecture and API details
- [Web App Documentation](web-app/README.md) - Frontend setup and development
- [Agents Documentation](server/AGENTS.md) - AI agents overview and configuration
- [Authentication Guide](server/docs/authentication.md) - Clerk setup
- [GDPR Compliance](server/docs/gdpr-compliance-guide.md) - Data privacy implementation

## 🛠️ Troubleshooting

### Docker issues

```bash
# Clear everything and rebuild
make clean
make rebuild
```

### Database issues

```bash
# Start only the database
make docker-run-db ENV=development
```

### Port conflicts

Ensure these ports are available: `3000` (web), `3001` (Grafana), `8000` (API), `8080` (cAdvisor), `9090` (Prometheus), `5432` (PostgreSQL)
