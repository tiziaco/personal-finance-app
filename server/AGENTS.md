# AI Agent Development Guide

This document provides essential guidelines for AI agents working on this LangGraph FastAPI Agent project.

## Project Overview

This is a production-ready AI agent application built with:
- **LangGraph** for stateful, multi-step AI agent workflows
- **FastAPI** for high-performance async REST API endpoints
- **Langfuse** for LLM observability and tracing
- **PostgreSQL + pgvector** for long-term memory storage (mem0ai)
- **Clerk** for authentication (JWT verification + JIT user provisioning)
- **Prometheus + Grafana** for monitoring

## Quick Reference: Critical Rules

### Import Rules
- **All imports MUST be at the top of the file** - never add imports inside functions or classes

### Logging Rules
- Use **structlog** for all logging
- Log messages must be **lowercase_with_underscores** (e.g., `"user_login_successful"`)
- **NO f-strings in structlog events** - pass variables as kwargs
- Use `logger.exception()` instead of `logger.error()` to preserve tracebacks
- Example: `logger.info("chat_request_received", conversation_id=conversation_id, message_count=len(messages))`
- **HTTP access logs** are handled by `AccessLogMiddleware` - never log access info manually
- **Uvicorn access logs** are silenced - all HTTP logging goes through structlog
- Use `component` field to categorize logs: `logger.bind(component="api-access")`, `logger.bind(component="service")`

### Retry Rules
- **Always use tenacity library** for retry logic
- Configure with exponential backoff
- Example: `@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))`

### Output Rules
- **Always enable rich library** for formatted console outputs
- Use rich for progress bars, tables, panels, and formatted text

### Caching Rules
- **Only cache successful responses**, never cache errors
- Use appropriate cache TTL based on data volatility

### FastAPI Rules
- All routes must have rate limiting decorators
- Use dependency injection for services, database connections, and auth
- All database operations must be async

## Code Style Conventions

### Python/FastAPI
- Use `async def` for asynchronous operations
- Use type hints for all function signatures
- Prefer Pydantic models over raw dictionaries
- Use functional, declarative programming; avoid classes except for services and agents
- File naming: lowercase with underscores (e.g., `user_routes.py`)
- Use the RORO pattern (Receive an Object, Return an Object)

### Error Handling
- Use domain-specific exceptions that inherit from `ServiceError`
- Never raise `HTTPException` from services - only from HTTP layer if absolutely needed
- Let centralized exception handler catch and translate exceptions
- All exceptions automatically include correlation IDs for tracing
- Services raise domain exceptions with context: `raise UserNotFoundError("User not found", user_id=user_id)`

## LangGraph & LangChain Patterns

### Agent Structure

This project follows a scalable multi-agent architecture:

```
app/agents/
├── base/                    # Abstract BaseAgent class
├── shared/                  # Reusable components across agents
│   ├── memory/             # Long-term memory (mem0ai)
│   ├── checkpointing/      # PostgreSQL checkpointing
│   └── observability/      # Langfuse callbacks
└── chatbot/                # Specific agent implementations
    ├── graph.py            # Agent workflow (extends BaseAgent)
    ├── state.py            # Agent-specific state schema
    ├── prompts/            # Agent-specific prompts
    └── tools/              # Agent-specific tools
```

### Graph Structure
- Use `StateGraph` for building AI agent workflows
- Define clear state schemas using Pydantic models (see `app/agents/chatbot/state.py`)
- Each agent extends `BaseAgent` and implements `create_graph()`
- Use `CompiledStateGraph` for production workflows
- Implement `AsyncPostgresSaver` for checkpointing and persistence (see `app/agents/shared/checkpointing/`)
- Use `Command` for controlling graph flow between nodes

### Shared Components

**Memory (`app/agents/shared/memory/`)**
- `create_memory()` - Initialize mem0ai AsyncMemory instance
- `get_relevant_memory(user_id, query)` - Retrieve semantic memories
- `update_memory(user_id, messages, metadata)` - Store conversation context
- `delete_user_memory(user_id)` - Delete all memories for a user (GDPR erasure)

**Checkpointing (`app/agents/shared/checkpointing/`)**
- `create_connection_pool()` - PostgreSQL connection pool
- `create_postgres_saver()` - AsyncPostgresSaver for LangGraph

**Observability (`app/agents/shared/observability/`)**
- `create_graph_config(conversation_id, user_id)` - Standard graph config

### BaseAgent Pattern

All agents extend the abstract `BaseAgent` class which provides:

**Required Implementation:**
- `create_graph()` - Must be implemented to define the agent's workflow

**Provided Methods:**
- `get_response(messages, conversation_id, user_id)` - Get non-streaming response
- `get_stream_response(messages, conversation_id, user_id)` - Get streaming response  
- `get_chat_history(conversation_id)` - Retrieve conversation history
- `clear_chat_history(conversation_id)` - Clear conversation history

**Built-in Features:**
- Automatic memory integration (retrieval and updates)
- Langfuse tracing on all LLM calls
- Graph initialization and caching
- Message processing and filtering

### Tracing
- Use LangChain's `CallbackHandler` from Langfuse for tracing all LLM calls
- All LLM operations must have Langfuse tracing enabled

### Memory (mem0ai)
- Use `AsyncMemory` for semantic memory storage
- Store memories per user_id for personalized experiences
- Use async methods: `add()`, `get()`, `search()`, `delete()`

## Authentication & Security

- **Clerk** handles authentication — no login/register endpoints in this app
- Clerk JWTs are verified by `AuthMiddleware` (RS256); `clerk_id` is set on `request.state`
- Use `CurrentUser` dependency (`Annotated[User, Depends(get_current_user)]`) for protected endpoints
- Users are JIT-provisioned in the local DB on first request via `UserProvider`
- Conversation ownership is verified by the `UserConversation` dependency
- Store sensitive data in environment variables
- Validate all user inputs with Pydantic models

## Database Operations

- Use SQLModel for ORM models (combines SQLAlchemy + Pydantic)
- Define models in `app/models/` directory
- Use async database operations with asyncpg
- Use LangGraph's AsyncPostgresSaver for agent checkpointing

## Performance Guidelines

- Minimize blocking I/O operations
- Use async for all database and external API calls
- Implement caching for frequently accessed data
- Use connection pooling for database connections
- Optimize LLM calls with streaming responses

## Observability

- Integrate Langfuse for LLM tracing on all agent operations
- Export Prometheus metrics for API performance
- Use structured logging with context binding (correlation_id, conversation_id, user_id)
- Track LLM inference duration, token usage, and costs
- All requests automatically get a correlation_id from `asgi-correlation-id` middleware
- Correlation IDs are bound to logs and included in error responses for end-to-end tracing

## Testing & Evaluation

- Implement metric-based evaluations for LLM outputs (see `evals/` directory)
- Create custom evaluation metrics as markdown files in `evals/metrics/prompts/`
- Use Langfuse traces for evaluation data sources
- Generate JSON reports with success rates

## Configuration Management

- Use environment-specific files: `.env.development`, `.env.staging`, `.env.production`
- Set `APP_ENV` environment variable to control which config file loads
- Access settings via nested structure: `settings.database.HOST`, `settings.llm.MODEL`, etc.
- Never hardcode secrets or API keys
- See `app/core/config.py` for all available settings and their structure

## Configuration & Settings Access

### Settings Structure
The application uses Pydantic Settings with **nested models** organized by domain:

- `settings.database.*` - PostgreSQL configuration (HOST, PORT, DB, USER, PASSWORD, POOL_SIZE, etc.)
- `settings.langfuse.*` - Observability configuration (PUBLIC_KEY, SECRET_KEY, HOST)
- `settings.llm.*` - LLM configuration (OPENAI_API_KEY, DEFAULT_LLM_MODEL, MAX_TOKENS, MAX_LLM_CALL_RETRIES, etc.)
- `settings.memory.*` - Long-term memory configuration (MODEL, EMBEDDER_MODEL, COLLECTION_NAME)
- `settings.auth.*` - Clerk authentication (SECRET_KEY, AUTHORIZE_URL, TOKEN_URL)
- `settings.logging.*` - Logging configuration (DIR, LEVEL, FORMAT)
- `settings.rate_limits.*` - Rate limiting (DEFAULT, endpoints.CHAT, endpoints.LOGIN, etc.)
- `settings.evaluation.*` - Evaluation configuration (LLM, API_KEY, BASE_URL, SLEEP_TIME)
- `settings.cors.*` - CORS configuration (ALLOWED_ORIGINS)


### Secret Values
Sensitive settings (API keys, passwords) use `SecretStr` and must be unpacked:

```python
# ✅ Correct - unpack SecretStr
api_key = settings.llm.OPENAI_API_KEY.get_secret_value()
password = settings.database.PASSWORD.get_secret_value()

# ❌ Wrong - using SecretStr directly
api_key = settings.llm.OPENAI_API_KEY  # Returns SecretStr object, not the value!
```

## Key Dependencies

- **FastAPI** - Web framework
- **LangGraph** - Agent workflow orchestration
- **LangChain** - LLM abstraction and tools
- **Langfuse** - LLM observability and tracing
- **Pydantic v2** - Data validation and settings
- **structlog** - Structured logging
- **mem0ai** - Long-term memory management
- **PostgreSQL + pgvector** - Database and vector storage
- **SQLModel** - ORM for database models
- **tenacity** - Retry logic
- **rich** - Terminal formatting
- **asgi-correlation-id** - Request correlation ID tracking

## Exception Handling System

This template uses a **hierarchical exception handling system** that separates business logic from HTTP concerns and provides consistent error responses with correlation IDs.
services must raise domain exceptions (never HTTPException)
### Architecture

**Service Layer** → Raises domain exceptions → **Exception Handler** → Returns standardized JSON

### Service-Specific Exceptions

Services are organized in packages with their own exception hierarchies:

- `app/services/user/` - `UserNotFoundError`, `UserAlreadyExistsError`, `InvalidCredentialsError`
- `app/services/conversation/` - `ConversationNotFoundError`, `ConversationAccessDeniedError`
- `app/services/llm/` - `LLMServiceError`, `LLMRateLimitError`, `LLMTimeoutError`, `LLMFallbackExhaustedError`

All inherit from base exceptions in `app/exceptions/base.py`:
- `ServiceError` - Base for all domain exceptions
- `ValidationError` - Input validation failures (422)
- `AuthenticationError` - Auth failures (401)
- `AuthorizationError` - Permission failures (403)
- `NotFoundError` - Resource not found (404)
- `ConflictError` - Resource conflicts (409)
- `DatabaseError` - Database errors (500/503)

### How to Use
- ❌ Raising `HTTPException` from services (use domain exceptions instead)
- ❌ Adding try-except blocks in endpoints (let centralized handler catch)
- ❌ Forgetting to pass context kwargs when raising domain exceptions

**In Services:**
```python
from app.services.user.exceptions import UserNotFoundError

async def get_user(user_id: str) -> User:
    user = await user_repository.get_by_id(session, user_id)
    if not user:
        raise UserNotFoundError(
            f"User {user_id} not found",
            user_id=user_id  # Context for logging
        )
    return user
```

**In Endpoints:**
```python
# No try-except needed! Handler catches automatically
@router.get("/users/{user_id}")
async def get_user_endpoint(user_id: str):
    return await user_service.get_user(user_id)
```

**Error Response Format:**
```json
{
  "error": "USER_NOT_FOUND",
  "message": "User abc-123 not found",
  "correlation_id": "a1b2c3d4",
  "details": {
    "user_id": "abc-123"
  }
}
```

### Exception Translation Layers

**Validation Layer** (`app/utils/`):
- `sanitize_email()`, `validate_password_strength()` raise `ValidationError`
- Include field name and validation context

**Database Layer** (`app/api/dependencies/database.py`):
- SQLAlchemy exceptions translated to `DatabaseError`, `DatabaseConflictError`, `DatabaseConnectionError`
- Happens at session commit in dependency

**LLM Layer** (`app/services/llm/`):
- OpenAI exceptions translated after tenacity retries exhausted
- Preserves original retry logic, adds translation wrapper
- `RateLimitError` → `LLMRateLimitError`, `APITimeoutError` → `LLMTimeoutError`

### Correlation IDs

All requests get a unique correlation ID:
1. `CorrelationIdMiddleware` generates or extracts from `x-correlation-id` header
2. Automatically bound to all log messages
3. Included in error responses
4. Use for tracing requests across services and logs

### Adding New Exceptions

1. Create exception in service package:
```python
# app/services/payment/exceptions.py
from app.exceptions.base import ServiceError

class PaymentFailedError(ServiceError):
    status_code = 402
    error_code = "PAYMENT_FAILED"
```

2. Raise with context:
```python
raise PaymentFailedError(
    "Payment processing failed",
    transaction_id=tx_id,
    amount=amount,
    reason=error_msg
)
```

3. Handler catches automatically - no endpoint changes needed!

## GDPR Compliance

This project implements basic GDPR "right to erasure" compliance. When a user requests account deletion (`DELETE /api/v1/auth/me`), the following is performed atomically:

1. **Clerk deletion** — user is removed from Clerk, immediately invalidating all JWTs
2. **Conversation soft-delete** — conversation metadata records are soft-deleted (non-PII kept for referential integrity)
3. **LangGraph checkpoint deletion** — all messages are hard-deleted from checkpoint tables (`clear_chat_history`)
4. **mem0 memory deletion** — all extracted long-term memory facts are deleted (`delete_user_memory`)
5. **User anonymization** — PII fields (email, name, avatar) are replaced with generic values; conversation names are cleared
6. **Cache invalidation** — the in-memory `UserProvider` cache is purged

### Model Design

- `AnonymizableMixin` — applied to `User`; provides `anonymize_user()` which clears all PII fields
- `SoftDeleteMixin` — applied to `Conversation`; use soft delete for non-PII records, never for user personal data
- Individual conversation deletion (`DELETE /api/v1/conversation/{id}`) also clears LangGraph data and soft-deletes the record

### Rules

- ❌ Never use `SoftDeleteMixin` for `User` — it leaves PII in the database
- ❌ Never add PII fields to `Conversation` without also clearing them in `User.anonymize_user()`
- ✅ New models with PII should use `AnonymizableMixin` and implement an `anonymize_*()` method
- ✅ Always call `agent.clear_chat_history()` before soft-deleting a conversation

## 10 Commandments for This Project

1. All routes must have rate limiting decorators
2. All LLM operations must have Langfuse tracing
3. All async operations must have proper error handling
4. All logs must follow structured logging format with lowercase_underscore event names
5. All retries must use tenacity library
6. All console outputs should use rich formatting
7. All caching should only store successful responses
8. All imports must be at the top of files
9. All database operations must be async
10. All endpoints must have proper type hints, Pydantic models, and access settings via nested structure

## Common Pitfalls to Avoid

- ❌ Using f-strings in structlog events
- ❌ Adding imports inside functions
- ❌ Forgetting rate limiting decorators on routes
- ❌ Missing Langfuse tracing on LLM calls
- ❌ Caching error responses
- ❌ Using `logger.error()` instead of `logger.exception()` for exceptions
- ❌ Blocking I/O operations without async
- ❌ Hardcoding secrets or API keys
- ❌ Missing type hints on function signatures
- ❌ Using SecretStr directly without `.get_secret_value()` for sensitive fields
- ❌ Manually logging HTTP access info (use AccessLogMiddleware instead)
- ❌ Enabling uvicorn's native access logs (they're silenced for structlog integration)

## When Making Changes

Before modifying code:
1. Read the existing implementation first
2. Check for related patterns in the codebase
3. Ensure consistency with existing code style
4. Add appropriate logging with structured format
5. Include error handling with early returns
6. Add type hints and Pydantic models
7. Verify Langfuse tracing is enabled for LLM calls

## References

- LangGraph Documentation: https://langchain-ai.github.io/langgraph/
- LangChain Documentation: https://python.langchain.com/docs/
- FastAPI Documentation: https://fastapi.tiangolo.com/
- Langfuse Documentation: https://langfuse.com/docs