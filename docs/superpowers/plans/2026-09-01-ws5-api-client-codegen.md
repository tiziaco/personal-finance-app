# WS5 — Typed API Client Codegen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace hand-written API access with TanStack Query hooks, TypeScript types and Zod schemas generated from the FastAPI OpenAPI spec, guarded by a drift check that fails when the committed artifacts stop matching the code.

**Architecture:** `server/openapi.json` is a committed artifact and the contract boundary. Two orval targets read it: a react-query target emitting per-tag hooks plus flat schema types, and a zod target emitting per-tag validators. Every generated call routes through a hand-written **hook** mutator (`useApiFetch`), which takes its token from `@app/auth` — so there is no module-level client singleton and no `ApiClientProvider`.

**Tech Stack:** FastAPI + Pydantic v2 (server), orval 8.27.0, TanStack Query v5, Zod 4, Next.js 16, pnpm workspaces, pytest.

**Spec:** `docs/superpowers/specs/2026-09-01-ws5-api-client-codegen-design.md`

## Global Constraints

- **Do not widen the role seam.** Nothing outside `@app/auth` may import `useAuth`/`useUser` from `@clerk/nextjs`. `@app/api-client` depends on `@app/auth`, never on Clerk.
- **Never hand-edit anything under `packages/api-client/src/generated/`.** orval's `clean: true` deletes that tree on every run.
- **Hand-written API request/response types are defects.** After this plan, no such type exists anywhere under `web-app/`.
- **The spec export and the client regeneration land in the same commit.** Splitting them is what `make check-contract` exists to catch.
- **Never surface server error text in the UI.** Toasts map an HTTP status to curated copy from `src/lib/messages.ts`.
- **Exact versions:** `orval` pinned to `8.27.0` (not a caret — the generated tree is committed). `prettier` pinned to `3.9.6`.
- **Operation ids are camelCase and explicit** (`getMe`, `listConversations`). An operation id is a public frontend symbol; renaming a handler is a breaking change.
- **Routes tagged `streaming` are exempt** from the response-body rule and excluded from codegen.
- Server commands run from `server/`. Frontend commands run from `web-app/`. `make` targets without a `-C` run from the repo root.

---

## File Structure

**Server**

| File | Responsibility |
|---|---|
| `server/app/schemas/system.py` | *Create.* Response models for `/`, `/health`, `/ready`. |
| `server/app/api/system/health.py` | *Modify.* Declare response models and operation ids; stop emitting a polymorphic `agents` value. |
| `server/app/api/v1/chatbot.py` | *Modify.* `tags=["streaming"]` on the SSE route; `status_code=204` on `clearChatHistory`. |
| `server/app/api/v1/conversation.py` | *Modify.* `status_code=204` on `deleteConversation`. |
| `server/scripts/export_openapi.py` | *Create.* Deterministic spec dump. |
| `server/Makefile` | *Modify.* `export-openapi` target. |
| `server/openapi.json` | *Create, committed.* The contract artifact. |
| `server/CLAUDE.md` | *Modify.* The API contract convention. |
| `server/tests/unit/schemas/test_system_schemas.py` | *Create.* System response model validation. |
| `server/tests/unit/api/test_openapi_contract.py` | *Create.* The convention, enforced mechanically. |
| `server/tests/unit/scripts/test_export_openapi.py` | *Create.* Export determinism. |

**Frontend**

| File | Responsibility |
|---|---|
| `web-app/packages/auth/src/provider.tsx` | *Modify.* Expose `getToken` on the auth context. |
| `web-app/packages/api-client/package.json` | *Create.* Subpath exports, pinned toolchain. |
| `web-app/packages/api-client/tsconfig.json` | *Create.* |
| `web-app/packages/api-client/orval.config.ts` | *Create.* Two targets, one input. |
| `web-app/packages/api-client/src/errors.ts` | *Create.* `ApiError`. |
| `web-app/packages/api-client/src/use-api-fetch.ts` | *Create.* The hook mutator. |
| `web-app/packages/api-client/src/index.ts` | *Create.* Public runtime surface. |
| `web-app/packages/api-client/scripts/postgen.mjs` | *Create.* Barrel regeneration. |
| `web-app/packages/api-client/src/generated/**` | *Generated, committed.* |
| `web-app/packages/ui/src/types/nav.ts` | *Create.* `NavItem`, moved from `@app/types`. |
| `web-app/packages/types/**` | *Delete.* |
| `web-app/apps/*/src/lib/messages.ts` | *Create.* Curated toast copy. |
| `web-app/apps/*/src/providers/query-provider.tsx` | *Modify.* Error mapping, toast gating, retry predicate. |
| `web-app/apps/*/src/hooks/use-server-status.ts` | *Modify.* Consume the generated hook. |
| `web-app/apps/*/src/lib/api/health.ts` | *Delete.* |

**Guardrails**

| File | Responsibility |
|---|---|
| `scripts/check-contract.sh` | *Create.* Regenerate both artifacts, fail on drift. |
| `Makefile` | *Modify.* `check-contract` target. |
| `.github/workflows/api-contract.yml` | *Create.* The repo's first CI workflow. |
| `docs/api-client-codegen-setup.md` | *Modify.* Correct the portable guide. |

---

## Task 1: Typed system responses

The three system routes are annotated `Dict[str, Any]`, so the schema emits `additionalProperties: true` and orval would generate `{[key: string]: unknown}`. `/ready` is worse than untyped: its `agents` value is an object keyed by agent name on the success path, and either `{"status": ..., "details": ...}` or a dict containing a bare `"error"` string on the failure paths. That polymorphism is why the hand-written `HealthResponse` in `@app/types` was already wrong.

This task types all three and flattens `agents` to a single shape.

**Files:**
- Create: `server/app/schemas/system.py`
- Create: `server/tests/unit/schemas/test_system_schemas.py`
- Modify: `server/app/api/system/health.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `RootResponse`, `HealthResponse`, `ReadinessResponse`, `ComponentsStatus`, `DatabaseStatus`, `ConnectionPoolStats`, `AgentStatus` in `app.schemas.system`. Task 2 asserts these appear as `$ref`s in the schema; Task 5 generates TypeScript from them.

- [ ] **Step 1: Write the failing test**

Create `server/tests/unit/schemas/test_system_schemas.py`:

```python
"""Tests for app.schemas.system — the response models for /, /health and /ready."""

from datetime import datetime, UTC

import pytest
from pydantic import ValidationError

from app.core.config import Environment
from app.schemas.system import (
    AgentStatus,
    ComponentsStatus,
    ConnectionPoolStats,
    DatabaseStatus,
    HealthResponse,
    ReadinessResponse,
    RootResponse,
)

pytestmark = pytest.mark.unit


def _components(**overrides) -> ComponentsStatus:
    defaults = dict(
        api="healthy",
        database=DatabaseStatus(
            status="healthy",
            connection_pool=ConnectionPoolStats(
                size=5, checked_in=5, checked_out=0, overflow=0, total=5
            ),
        ),
        agents={"chatbot": AgentStatus(ready=True, graph_compiled=True)},
        agents_healthy=True,
    )
    defaults.update(overrides)
    return ComponentsStatus(**defaults)


class TestRootResponse:
    def test_valid(self):
        model = RootResponse(
            name="FastAPI LangGraph Clerk",
            version="1.0.0",
            status="healthy",
            environment=Environment.DEVELOPMENT,
            swagger_url="/docs",
            redoc_url="/redoc",
        )
        assert model.version == "1.0.0"


class TestHealthResponse:
    def test_valid_healthy(self):
        model = HealthResponse(status="healthy", timestamp=datetime.now(UTC))
        assert model.status == "healthy"

    def test_valid_degraded(self):
        model = HealthResponse(status="degraded", timestamp=datetime.now(UTC))
        assert model.status == "degraded"

    def test_rejects_unknown_status(self):
        with pytest.raises(ValidationError):
            HealthResponse(status="on fire", timestamp=datetime.now(UTC))


class TestComponentsStatus:
    def test_agents_is_a_mapping_of_agent_name_to_status(self):
        model = _components()
        assert model.agents["chatbot"].ready is True
        assert model.agents["chatbot"].graph_compiled is True

    def test_agents_defaults_to_empty_and_carries_an_error_string(self):
        model = _components(
            agents={}, agents_healthy=False, agents_error="Agents not initialized"
        )
        assert model.agents == {}
        assert model.agents_error == "Agents not initialized"

    def test_agents_rejects_a_bare_string_value(self):
        # This is the shape that made the hand-written frontend type wrong:
        # an object on the success path, a string on the failure path.
        with pytest.raises(ValidationError):
            _components(agents={"error": "Agents not initialized"})


class TestReadinessResponse:
    def test_valid(self):
        model = ReadinessResponse(
            status="healthy",
            version="1.0.0",
            environment=Environment.DEVELOPMENT,
            components=_components(),
            timestamp=datetime.now(UTC),
        )
        assert model.components.database.connection_pool.total == 5

    def test_requires_components(self):
        with pytest.raises(ValidationError):
            ReadinessResponse(
                status="healthy",
                version="1.0.0",
                environment=Environment.DEVELOPMENT,
                timestamp=datetime.now(UTC),
            )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/schemas/test_system_schemas.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.schemas.system'`

- [ ] **Step 3: Write the schemas**

Create `server/app/schemas/system.py`:

```python
"""Response schemas for the system endpoints (/, /health, /ready).

These models are the contract for the frontend's server-status widget. Before
they existed the three routes were annotated `Dict[str, Any]`, which emits
`additionalProperties: true` into the OpenAPI schema and generates
`{[key: string]: unknown}` on the client — type safety erased silently.
"""

from datetime import datetime
from typing import (
    Dict,
    Literal,
    Optional,
)

from pydantic import (
    BaseModel,
    Field,
)

from app.core.config import Environment


class ConnectionPoolStats(BaseModel):
    """SQLAlchemy connection pool counters."""

    size: int = Field(..., description="Configured pool size")
    checked_in: int = Field(..., description="Connections idle in the pool")
    checked_out: int = Field(..., description="Connections currently in use")
    overflow: int = Field(..., description="Connections created beyond the pool size")
    total: int = Field(..., description="size + overflow")


class DatabaseStatus(BaseModel):
    """Database connectivity and pool state."""

    status: Literal["healthy", "unhealthy"] = Field(..., description="Database reachability")
    connection_pool: ConnectionPoolStats = Field(..., description="Pool counters")


class AgentStatus(BaseModel):
    """Readiness of a single agent."""

    ready: bool = Field(..., description="Agent reports itself ready")
    graph_compiled: bool = Field(..., description="LangGraph graph is compiled")


class ComponentsStatus(BaseModel):
    """Per-component readiness detail.

    `agents` is always a mapping of agent name to status — never a bare string,
    and never wrapped in an envelope. The "agents were never initialised"
    condition is carried by `agents_error`, so the value's shape does not
    depend on the outcome.
    """

    api: Literal["healthy"] = Field(..., description="The API itself is serving")
    database: DatabaseStatus = Field(..., description="Database component")
    agents: Dict[str, AgentStatus] = Field(
        default_factory=dict, description="Agent name to readiness status"
    )
    agents_healthy: bool = Field(..., description="Every registered agent is ready")
    agents_error: Optional[str] = Field(
        None, description="Set when the agent registry was never initialised"
    )


class RootResponse(BaseModel):
    """Basic API metadata returned by GET /."""

    name: str = Field(..., description="Project name")
    version: str = Field(..., description="Application version")
    status: Literal["healthy"] = Field(..., description="Always healthy if this responds")
    environment: Environment = Field(..., description="Deployment environment")
    swagger_url: str = Field(..., description="Path to the Swagger UI")
    redoc_url: str = Field(..., description="Path to the ReDoc UI")


class HealthResponse(BaseModel):
    """Minimal public health check returned by GET /health."""

    status: Literal["healthy", "degraded"] = Field(..., description="Overall health")
    timestamp: datetime = Field(..., description="When the check ran")


class ReadinessResponse(BaseModel):
    """Detailed authenticated readiness returned by GET /ready."""

    status: Literal["healthy", "degraded"] = Field(..., description="Overall readiness")
    version: str = Field(..., description="Application version")
    environment: Environment = Field(..., description="Deployment environment")
    components: ComponentsStatus = Field(..., description="Per-component detail")
    timestamp: datetime = Field(..., description="When the check ran")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/schemas/test_system_schemas.py -v`
Expected: PASS (9 tests)

- [ ] **Step 5: Wire the models into the routes**

In `server/app/api/system/health.py`, change the imports at the top of the file:

```python
from datetime import datetime

from fastapi import (
    APIRouter,
    Request,
    Response,
    status,
)
from sqlalchemy.ext.asyncio import AsyncEngine

from app.api.dependencies.authentication import CurrentUser
from app.core.config import settings
from app.core.limiter import limiter
from app.core.logging import logger
from app.database.engine import health_check as db_health_check
from app.schemas.system import (
    AgentStatus,
    ComponentsStatus,
    ConnectionPoolStats,
    DatabaseStatus,
    HealthResponse,
    ReadinessResponse,
    RootResponse,
)
```

`Dict`, `Any` and `JSONResponse` are no longer used — remove those imports. The 503 status is now set through the injected `Response` rather than by constructing a `JSONResponse`, which is what lets `response_model` actually validate the payload; returning a `JSONResponse` bypasses validation and would let the schema drift from reality again.

Replace the three route definitions:

```python
@router.get(
    "/",
    operation_id="getRoot",
    response_model=RootResponse,
    summary="Get API information",
    description="Retrieve basic API metadata including version, environment, and documentation URLs.",
)
@limiter.limit(settings.rate_limits.endpoints.ROOT[0])
async def root(request: Request) -> RootResponse:
    """Root endpoint returning basic API information."""
    logger.info("root_endpoint_called")
    return RootResponse(
        name=settings.PROJECT_NAME,
        version=settings.VERSION,
        status="healthy",
        environment=settings.ENVIRONMENT,
        swagger_url="/docs",
        redoc_url="/redoc",
    )


@router.get(
    "/health",
    operation_id="getHealth",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "System is degraded"}},
    summary="Check API health status",
    description="Minimal public health check endpoint for container orchestration and load balancers. Returns basic status without sensitive details.",
)
@limiter.limit(settings.rate_limits.endpoints.HEALTH[0])
async def health_check(request: Request, response: Response) -> HealthResponse:
    """Minimal public health check endpoint for orchestrators and load balancers."""
    engine: AsyncEngine = request.app.state.engine
    db_healthy = await db_health_check(engine)

    agents_healthy = False
    if hasattr(request.app.state, "agents"):
        agents_healthy = all(
            agent.is_ready() for agent in request.app.state.agents.values()
        )

    overall_healthy = db_healthy and agents_healthy
    if not overall_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status="healthy" if overall_healthy else "degraded",
        timestamp=datetime.now(),
    )


@router.get(
    "/ready",
    operation_id="getReadiness",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse, "description": "System is degraded"}},
    summary="Get detailed readiness status",
    description="Detailed readiness check with component-level health information. Requires authentication. Use this endpoint for monitoring dashboards and operational visibility.",
)
@limiter.limit(settings.rate_limits.endpoints.READY[0])
async def readiness_check(
    user: CurrentUser, request: Request, response: Response
) -> ReadinessResponse:
    """Detailed readiness check for authenticated operations teams."""
    logger.info("readiness_check_called", user_id=user.id)

    engine: AsyncEngine = request.app.state.engine
    db_healthy = await db_health_check(engine)

    pool_stats = ConnectionPoolStats(
        size=engine.pool.size(),
        checked_in=engine.pool.checkedin(),
        checked_out=engine.pool.checkedout(),
        overflow=engine.pool.overflow(),
        total=engine.pool.size() + engine.pool.overflow(),
    )

    # `agents` keeps one shape regardless of outcome: a mapping of agent name to
    # status. The "never initialised" case is carried by agents_error, not by
    # substituting a different value type.
    agents: dict[str, AgentStatus] = {}
    agents_error: str | None = None
    agents_healthy = False

    if hasattr(request.app.state, "agents"):
        agents_healthy = True
        for agent_name, agent_instance in request.app.state.agents.items():
            is_ready = agent_instance.is_ready()
            agents[agent_name] = AgentStatus(ready=is_ready, graph_compiled=is_ready)
            if not is_ready:
                agents_healthy = False
    else:
        agents_error = "Agents not initialized"

    overall_healthy = db_healthy and agents_healthy
    if not overall_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="healthy" if overall_healthy else "degraded",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
        components=ComponentsStatus(
            api="healthy",
            database=DatabaseStatus(
                status="healthy" if db_healthy else "unhealthy",
                connection_pool=pool_stats,
            ),
            agents=agents,
            agents_healthy=agents_healthy,
            agents_error=agents_error,
        ),
        timestamp=datetime.now(),
    )
```

- [ ] **Step 6: Verify the schema no longer emits untyped objects**

Run:

```bash
cd server && APP_ENV=development PYTHONPATH=. uv run python -c "
from app.main import app
import json
spec = app.openapi()
for path in ('/', '/health', '/ready'):
    op = spec['paths'][path]['get']
    schema = op['responses']['200']['content']['application/json']['schema']
    print(path, op['operationId'], json.dumps(schema))
" 2>/dev/null
```

Expected: three lines, each showing an explicit `operationId` (`getRoot`, `getHealth`, `getReadiness`) and a `\$ref` to `#/components/schemas/...` — no `additionalProperties`.

- [ ] **Step 7: Run the full unit suite**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/ -v -m unit`
Expected: PASS, no regressions.

- [ ] **Step 8: Commit**

```bash
git add server/app/schemas/system.py server/app/api/system/health.py server/tests/unit/schemas/test_system_schemas.py
git commit -m "feat(server): typed response models for the system endpoints

/, /health and /ready were annotated Dict[str, Any], which emits
additionalProperties: true and would generate {[key: string]: unknown}
on the client. They now declare RootResponse, HealthResponse and
ReadinessResponse, plus explicit camelCase operation ids.

/ready's agents value was polymorphic — a mapping of agent name to
status on the success path, an envelope or a dict holding a bare error
string on the failure paths. That is why the hand-written HealthResponse
in @app/types was wrong. agents is now always a mapping; the
never-initialised case is carried by agents_error.

Both degraded paths set the 503 through the injected Response instead of
returning JSONResponse, so response_model actually validates the payload."
```

---

## Task 2: The contract convention, enforced

Task 1 fixed three routes. This task writes the rule down and makes a test enforce it, so the next endpoint cannot reintroduce an auto-generated operation id or an untyped response.

Two routes still violate it: `deleteConversation` and `clearChatHistory` return 200 with no schema. And `streamChatMessage` is SSE — it has no JSON body by nature, so the convention grants streaming routes an explicit exemption and codegen excludes them by tag.

**Files:**
- Create: `server/tests/unit/api/test_openapi_contract.py`
- Modify: `server/app/api/v1/conversation.py`
- Modify: `server/app/api/v1/chatbot.py`
- Modify: `server/CLAUDE.md`

**Interfaces:**
- Consumes: the response models from Task 1.
- Produces: the `streaming` tag, which Task 5's `orval.config.ts` excludes via `input.filters`.

- [ ] **Step 1: Write the failing test**

Create `server/tests/unit/api/test_openapi_contract.py`:

```python
"""The OpenAPI schema satisfies the API contract convention.

The convention is documented in server/CLAUDE.md. It exists because the schema
is a published artifact: server/openapi.json is committed and generates the
frontend's hooks, types and validators. A route that violates any rule below
produces a broken or misleading client symbol, silently.
"""

import re

import pytest

from app.main import app

pytestmark = pytest.mark.unit

HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}

# Explicit ids are camelCase: getMe, listConversations. FastAPI's auto-generated
# ids are snake_case and carry the path and method: health_check_health_get.
CAMEL_CASE = re.compile(r"^[a-z][A-Za-z0-9]*$")

# Streaming routes return a StreamingResponse and have no JSON body to declare.
# They are excluded from codegen by this tag; WS7 owns the hand-written client.
STREAMING_TAG = "streaming"


def _operations():
    """Yield (path, method, operation) for every operation in the schema."""
    schema = app.openapi()
    for path, item in schema["paths"].items():
        for method, operation in item.items():
            if method.lower() in HTTP_METHODS:
                yield path, method.lower(), operation


def _label(path: str, method: str) -> str:
    return f"{method.upper()} {path}"


class TestOperationIds:
    def test_every_operation_declares_an_explicit_camel_case_id(self):
        offenders = [
            f"{_label(p, m)} -> {op.get('operationId')!r}"
            for p, m, op in _operations()
            if not CAMEL_CASE.match(op.get("operationId", ""))
        ]
        assert not offenders, (
            "These routes rely on FastAPI's auto-generated operation_id. It becomes "
            "the frontend hook name, so declare an explicit camelCase operation_id: "
            + "; ".join(offenders)
        )

    def test_operation_ids_are_unique(self):
        seen: dict[str, str] = {}
        duplicates = []
        for path, method, operation in _operations():
            op_id = operation.get("operationId", "")
            if op_id in seen:
                duplicates.append(f"{op_id!r}: {seen[op_id]} and {_label(path, method)}")
            seen[op_id] = _label(path, method)
        assert not duplicates, (
            "Duplicate operation ids collide into one generated symbol: "
            + "; ".join(duplicates)
        )


class TestTags:
    def test_every_operation_declares_a_tag(self):
        offenders = [
            _label(p, m) for p, m, op in _operations() if not op.get("tags")
        ]
        assert not offenders, (
            "Tags become the generated client's directory names and module "
            "boundaries. Untagged routes collapse into a 'default' bucket: "
            + ", ".join(offenders)
        )


class TestResponses:
    def test_every_operation_declares_a_response_body_or_204(self):
        offenders = []
        for path, method, operation in _operations():
            if STREAMING_TAG in operation.get("tags", []):
                continue
            responses = operation.get("responses", {})
            if "204" in responses:
                continue
            success_codes = [c for c in responses if c.startswith("2")]
            if not any(responses[c].get("content") for c in success_codes):
                offenders.append(_label(path, method))
        assert not offenders, (
            "A route with no declared response body generates `unknown` on the "
            "client. Declare a response_model, or status_code=204 if it returns "
            "no body: " + ", ".join(offenders)
        )

    def test_no_response_schema_is_an_untyped_object(self):
        offenders = []
        for path, method, operation in _operations():
            if STREAMING_TAG in operation.get("tags", []):
                continue
            for code, response in operation.get("responses", {}).items():
                if not code.startswith("2"):
                    continue
                schema = response.get("content", {}).get("application/json", {}).get("schema", {})
                if schema.get("additionalProperties") is True:
                    offenders.append(f"{_label(path, method)} ({code})")
        assert not offenders, (
            "`Dict[str, Any]` emits additionalProperties: true, which generates "
            "{[key: string]: unknown} and erases type safety. Declare a Pydantic "
            "response model: " + ", ".join(offenders)
        )
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/api/test_openapi_contract.py -v`
Expected: FAIL. `test_every_operation_declares_a_response_body_or_204` reports `DELETE /api/v1/conversation/conversation/{conversation_id}`, `DELETE /api/v1/chatbot/chat/{conversation_id}/messages`, and `POST /api/v1/chatbot/chat/{conversation_id}/stream`. The other four tests pass.

- [ ] **Step 3: Add 204 to the two bodyless deletes**

In `server/app/api/v1/conversation.py`, add `status_code=204` to the delete route decorator so it matches `deleteMe`:

```python
@router.delete(
    "/conversation/{conversation_id}",
    operation_id="deleteConversation",
    status_code=204,
    summary="Delete a chat conversation",
    description="Remove a chat conversation and permanently delete all associated messages."
)
```

In `server/app/api/v1/chatbot.py`, the same for the clear-history route:

```python
@router.delete(
    "/chat/{conversation_id}/messages",
    operation_id="clearChatHistory",
    status_code=204,
    summary="Clear chat history",
    description="Remove all messages from the specified chat conversation."
)
```

- [ ] **Step 4: Give the SSE route its own tag**

In `server/app/api/v1/chatbot.py`, add a per-route tag override to the stream route. The router is included with `tags=["chatbot"]`; this override replaces that for this route only, which is what lets orval exclude it by tag while the route stays visible in Swagger.

```python
@router.post(
    "/chat/{conversation_id}/stream",
    operation_id="streamChatMessage",
    tags=["streaming"],
    summary="Stream chat response in real-time",
    description="Send a message and receive the AI agent's response as a server-sent event stream."
)
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/api/test_openapi_contract.py -v`
Expected: PASS (5 tests)

- [ ] **Step 6: Document the convention**

Append to `server/CLAUDE.md`, after the "Exception Handling" section:

````markdown
---

## API Contract

`server/openapi.json` is a committed artifact. It generates the frontend's
TanStack Query hooks, TypeScript types and Zod validators, so the schema is a
published interface, not a by-product. Every route must therefore declare:

- **An explicit tag.** Tags become directory names and module boundaries in the
  generated client. Untagged routes collapse into a `default` bucket.
- **An explicit camelCase `operation_id`** — `getMe`, `listConversations`.
  FastAPI's auto-generated ids (`health_check_health_get`) become hook names
  like `useHealthCheckHealthGet`.
- **Either a `response_model` or `status_code=204`.** A route with neither
  generates `unknown` on the client. `Dict[str, Any]` is not a response model:
  it emits `additionalProperties: true` and generates
  `{[key: string]: unknown}`.

Two further rules:

- **Server-to-server routes declare `include_in_schema=False`.** The Clerk
  webhook receiver already does; the frontend must never get a hook for it.
- **Streaming routes declare `tags=["streaming"]`** and are exempt from the
  response-body rule. They have no JSON body, and orval excludes the tag. They
  remain visible in Swagger.

**`operation_id` is a public frontend symbol.** Renaming a handler renames a
hook. Treat it as a breaking change.

**Regenerate in the same commit.** After changing any route, run
`make export-openapi` here and `pnpm --filter @app/api-client gen:api` in
`web-app/`, and commit both outputs together. `make check-contract` at the repo
root does both and fails if the committed artifacts are stale.

`tests/unit/api/test_openapi_contract.py` enforces the three per-route rules
mechanically. It needs no database.
````

- [ ] **Step 7: Run the full unit suite**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/ -v -m unit`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add server/tests/unit/api/test_openapi_contract.py server/app/api/v1/conversation.py server/app/api/v1/chatbot.py server/CLAUDE.md
git commit -m "feat(server): enforce the API contract convention

Adds a unit test over app.openapi() asserting every operation declares an
explicit camelCase operation_id, a unique id, a tag, and either a response
body or 204 — and that no 2xx schema is an untyped object.

Fixes the two routes that failed it: deleteConversation and
clearChatHistory returned 200 with no schema and would generate unknown.
Both now declare status_code=204, matching deleteMe.

streamChatMessage moves to tags=['streaming']. SSE has no JSON body to
declare, so the convention exempts the tag and orval excludes it from
codegen; the route stays visible in Swagger. WS7 owns its client.

The convention is documented in server/CLAUDE.md so it survives the fork."
```

---

## Task 3: The OpenAPI export

**Files:**
- Create: `server/scripts/export_openapi.py`
- Create: `server/tests/unit/scripts/__init__.py`
- Create: `server/tests/unit/scripts/test_export_openapi.py`
- Modify: `server/Makefile`
- Create: `server/openapi.json` (generated, committed)

**Interfaces:**
- Consumes: the contract from Tasks 1 and 2.
- Produces: `export_spec(output_path: Path) -> Path` in `scripts/export_openapi.py`, and the committed `server/openapi.json` that Task 5's orval config reads.

- [ ] **Step 1: Write the failing test**

Create `server/tests/unit/scripts/__init__.py` (empty file), then `server/tests/unit/scripts/test_export_openapi.py`:

```python
"""Tests for scripts/export_openapi.py — the contract artifact must be deterministic."""

import json
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from export_openapi import export_spec  # noqa: E402

pytestmark = pytest.mark.unit


class TestExportSpec:
    def test_writes_parseable_json(self, tmp_path):
        target = export_spec(tmp_path / "openapi.json")
        spec = json.loads(target.read_text(encoding="utf-8"))
        assert spec["openapi"].startswith("3.")
        assert "/ready" in spec["paths"]

    def test_output_is_byte_identical_across_runs(self):
        # Dict ordering churn produces enormous meaningless diffs and defeats
        # review, so the dump sorts keys. Two runs must agree exactly.
        import tempfile

        with tempfile.TemporaryDirectory() as d:
            first = export_spec(Path(d) / "a.json").read_bytes()
            second = export_spec(Path(d) / "b.json").read_bytes()
        assert first == second

    def test_keys_are_sorted(self, tmp_path):
        target = export_spec(tmp_path / "openapi.json")
        spec = json.loads(target.read_text(encoding="utf-8"))
        assert list(spec.keys()) == sorted(spec.keys())

    def test_ends_with_a_trailing_newline(self, tmp_path):
        target = export_spec(tmp_path / "openapi.json")
        assert target.read_text(encoding="utf-8").endswith("}\n")
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/scripts/test_export_openapi.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'export_openapi'`

- [ ] **Step 3: Write the export script**

Create `server/scripts/export_openapi.py`:

```python
#!/usr/bin/env python3
"""Export the FastAPI OpenAPI spec to server/openapi.json.

FastAPI builds the spec from registered routes and Pydantic models via
`app.openapi()`, so no running server, network, or database is required — only
an environment that lets `from app.main import app` import cleanly. That is what
lets the drift check run in CI with no secrets configured.

The dump sorts keys and indents by two, because the output is committed and
reviewed: without sorting, dict ordering churn produces enormous meaningless
diffs.
"""

import json
import sys
from pathlib import Path

from app.main import app

DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "openapi.json"


def export_spec(output_path: Path = DEFAULT_OUTPUT) -> Path:
    """Write the OpenAPI spec to `output_path` and return it."""
    spec = app.openapi()
    with output_path.open("w", encoding="utf-8") as fp:
        json.dump(spec, fp, indent=2, sort_keys=True)
        fp.write("\n")
    return output_path


def main() -> int:
    target = export_spec()
    print(f"Wrote OpenAPI spec to {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `cd server && APP_ENV=test uv run pytest tests/unit/scripts/test_export_openapi.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Add the Makefile target**

In `server/Makefile`, add after the `format:` target:

```make
# The OpenAPI spec is a committed artifact: it generates the frontend client.
# Needs no database, no network and no secrets — app.openapi() builds the schema
# from registered routes.
export-openapi:
	@echo "Exporting OpenAPI spec to server/openapi.json"
	@APP_ENV=$${APP_ENV:-development} PYTHONPATH=. uv run python scripts/export_openapi.py
```

And add a line to the `help:` target, after the `format` entry:

```make
	@echo "  export-openapi: Export the OpenAPI spec to server/openapi.json"
```

- [ ] **Step 6: Generate and inspect the artifact**

Run: `cd server && make export-openapi`
Expected: `Wrote OpenAPI spec to .../server/openapi.json`

Then confirm the streaming route is present in the spec but tagged for exclusion, and that the webhook route is absent:

```bash
cd server && python3 -c "
import json
spec = json.load(open('openapi.json'))
ops = {op['operationId']: op.get('tags') for p in spec['paths'].values() for m, op in p.items() if isinstance(op, dict) and 'operationId' in op}
print('total operations:', len(ops))
print('streamChatMessage tags:', ops.get('streamChatMessage'))
print('clerkWebhook present:', 'clerkWebhook' in ops)
"
```

Expected: `streamChatMessage tags: ['streaming']` and `clerkWebhook present: False`.

- [ ] **Step 7: Commit**

```bash
git add server/scripts/export_openapi.py server/tests/unit/scripts/ server/Makefile server/openapi.json
git commit -m "feat(server): export the OpenAPI spec as a committed artifact

server/openapi.json becomes the contract boundary between the backend and
the frontend client. The dump sorts keys and indents by two so the diff is
reviewable; a test asserts two runs are byte-identical.

The export needs no database, no .env and no secrets — app.openapi()
builds the schema from registered routes — which is what lets the drift
check added later run in CI with nothing configured."
```

---

## Task 4: Expose `getToken` on the auth seam

`useAppAuth()` returns `{ user, role, isLoaded }`. The mutator in Task 5 needs a token, and `@app/auth`'s own docblock forbids components calling Clerk's `useAuth()` directly — a rule both copies of `use-server-status.ts` currently break. Adding `getToken` to the context is what lets `@app/api-client` depend on the seam instead of on Clerk.

**Files:**
- Modify: `web-app/packages/auth/src/provider.tsx`

**Interfaces:**
- Produces: `useAppAuth(): { user, role, isLoaded, getToken }` where `getToken: () => Promise<string | null>`. Task 5's `useApiFetch` consumes it.

- [ ] **Step 1: Add `getToken` to the context**

In `web-app/packages/auth/src/provider.tsx`, extend the interface, the default value, and the provider. Replace the `AuthContextValue` interface and the `AuthContext` default:

```tsx
interface AuthContextValue {
  /** The Clerk user object, or null/undefined while loading. */
  user: UserResource | null | undefined
  /** The current user's org role, or null if no active org context. */
  role: Role | null
  /** True once Clerk has finished initialising the session. */
  isLoaded: boolean
  /**
   * Returns a fresh JWT for the current session, or null when signed out.
   *
   * This is the only sanctioned way to reach a bearer token. @app/api-client's
   * mutator consumes it, which is what keeps that package dependent on this
   * seam rather than on Clerk.
   */
  getToken: () => Promise<string | null>
}

const AuthContext = createContext<AuthContextValue>({
  user: null,
  role: null,
  isLoaded: false,
  getToken: async () => null,
})
```

Then in `AuthProvider`, pull `getToken` off Clerk's `useAuth()` and pass it through:

```tsx
export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { isLoaded, orgRole, getToken } = useAuth()
  const { user } = useUser()
  const role = getUserRole(orgRole)

  return (
    <AuthContext.Provider value={{ user, role, isLoaded, getToken }}>
      {children}
    </AuthContext.Provider>
  )
}
```

Clerk's `getToken` accepts an options argument this context deliberately does not expose; the narrower `() => Promise<string | null>` is structurally compatible and keeps the seam small.

- [ ] **Step 2: Type-check**

Run: `cd web-app && pnpm --filter @app/auth exec tsc --noEmit`
Expected: PASS, no output.

- [ ] **Step 3: Commit**

```bash
git add web-app/packages/auth/src/provider.tsx
git commit -m "feat(auth): expose getToken on the auth context

useAppAuth() returned identity and role but no token, so anything needing
a bearer token had to call Clerk's useAuth() directly — which this
package's own docblock forbids, and which both copies of
use-server-status.ts do today.

Exposing it here lets @app/api-client depend on the portability seam
instead of on Clerk, so the B2C fork changes AuthProvider's internals and
nothing else."
```

---

## Task 5: The `@app/api-client` package

The largest task. Scaffolds the package, writes the three hand-written files, configures both orval targets, and commits the first generated tree.

**Files:**
- Create: `web-app/packages/api-client/package.json`
- Create: `web-app/packages/api-client/tsconfig.json`
- Create: `web-app/packages/api-client/orval.config.ts`
- Create: `web-app/packages/api-client/src/errors.ts`
- Create: `web-app/packages/api-client/src/use-api-fetch.ts`
- Create: `web-app/packages/api-client/src/index.ts`
- Create: `web-app/packages/api-client/scripts/postgen.mjs`
- Create: `web-app/packages/api-client/src/generated/**` (generated, committed)

**Interfaces:**
- Consumes: `useAppAuth().getToken` from Task 4; `server/openapi.json` from Task 3.
- Produces:
  - `ApiError` with `{ status: number, body: unknown, requestId: string | null }`, imported by Task 6's `query-provider.tsx`.
  - `useApiFetch()` — the mutator orval calls.
  - Generated `useGetReadiness(options?)` from `@app/api-client/endpoints/system`, consumed by Task 6. orval derives hook names as `use` + PascalCase(operationId), so `getReadiness` yields `useGetReadiness`.
  - Subpath exports `@app/api-client/endpoints/<tag>`, `@app/api-client/types`, `@app/api-client/zod/<tag>`.

- [ ] **Step 1: Create the package manifest**

Create `web-app/packages/api-client/package.json`:

```json
{
  "name": "@app/api-client",
  "version": "0.0.1",
  "private": true,
  "main": "./src/index.ts",
  "types": "./src/index.ts",
  "exports": {
    ".": "./src/index.ts",
    "./endpoints/*": "./src/generated/endpoints/*/index.ts",
    "./types": "./src/generated/types/index.ts",
    "./zod/*": "./src/generated/zod/*/index.ts"
  },
  "scripts": {
    "gen:api": "orval && node scripts/postgen.mjs",
    "type-check": "tsc --noEmit"
  },
  "dependencies": {
    "@app/auth": "workspace:*",
    "@tanstack/react-query": "^5.0.0",
    "zod": "^4.0.0"
  },
  "peerDependencies": {
    "react": "^19.0.0"
  },
  "devDependencies": {
    "@types/react": "^19.2.14",
    "orval": "8.27.0",
    "prettier": "3.9.6",
    "typescript": "^5.9.3"
  }
}
```

`orval` and `prettier` are pinned exactly, with no caret: the generated tree is committed, so a routine `pnpm install` must not rewrite hundreds of tracked files. `react` is a peer dependency — the package must never resolve its own React copy.

Create `web-app/packages/api-client/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true
  },
  "include": ["**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 2: Write the hand-written source**

Create `web-app/packages/api-client/src/errors.ts`:

```ts
/**
 * The single error type the application layer needs to know about.
 *
 * `requestId` is the server's correlation id, read from X-Request-ID.
 * CorrelationIdMiddleware stamps every request and binds the id to the
 * server's structured logs, so a client-side failure is traceable to a
 * server log line.
 */
export class ApiError extends Error {
  readonly status: number
  readonly body: unknown
  readonly requestId: string | null

  constructor(message: string, status: number, body: unknown, requestId: string | null) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.body = body
    this.requestId = requestId
  }
}
```

Create `web-app/packages/api-client/src/use-api-fetch.ts`:

```ts
"use client"

import { useCallback } from "react"
import { useAppAuth } from "@app/auth"

import { ApiError } from "./errors"

/**
 * The mutator every generated endpoint routes through.
 *
 * It is a hook, not a module-level singleton, and that is deliberate. A
 * module-scope client would be shared across concurrent requests in a Next.js
 * server process — one tenant's token serving another tenant's request — and
 * would freeze the first render's getToken closure. As a hook it reads the
 * current token on every call, needs no provider of its own, and makes the
 * provider ordering in the root layout irrelevant.
 *
 * orval recognises the `use` prefix and calls this inside each generated hook.
 */
function resolveBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL
  if (!url) {
    throw new Error("@app/api-client: NEXT_PUBLIC_API_URL is not set")
  }
  return url
}

async function parseErrorBody(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? ""
  try {
    if (contentType.includes("application/json")) return await response.json()
    return await response.text()
  } catch {
    return null
  }
}

export function useApiFetch() {
  const { getToken } = useAppAuth()

  return useCallback(
    async <T>(url: string, init?: RequestInit): Promise<T> => {
      const fullUrl = /^https?:\/\//i.test(url) ? url : `${resolveBaseUrl()}${url}`
      const headers = new Headers(init?.headers)

      const token = await getToken()
      if (token && !headers.has("authorization")) {
        headers.set("Authorization", `Bearer ${token}`)
      }

      // Only set a JSON content type for plain bodies. Never for FormData — the
      // browser must set its own multipart boundary — nor for Blob or ArrayBuffer.
      const body = init?.body
      if (
        body != null &&
        !headers.has("content-type") &&
        !(body instanceof FormData) &&
        !(body instanceof Blob) &&
        !(body instanceof ArrayBuffer)
      ) {
        headers.set("Content-Type", "application/json")
      }

      const response = await fetch(fullUrl, { ...init, headers })
      const requestId = response.headers.get("x-request-id")

      if (!response.ok) {
        throw new ApiError(
          response.statusText || "Request failed",
          response.status,
          await parseErrorBody(response),
          requestId,
        )
      }

      if (response.status === 204) return undefined as T
      if (response.headers.get("content-length") === "0") return undefined as T

      const contentType = response.headers.get("content-type") ?? ""
      if (contentType.includes("application/json")) return (await response.json()) as T

      return (await response.text()) as unknown as T
    },
    [getToken],
  )
}
```

Create `web-app/packages/api-client/src/index.ts`:

```ts
/**
 * The package's public runtime surface is deliberately tiny. Everything else is
 * reached through the subpath exports, so importing one tag does not pull in
 * the whole client.
 */
export { ApiError } from "./errors"
export { useApiFetch } from "./use-api-fetch"
```

- [ ] **Step 3: Write the orval config**

Create `web-app/packages/api-client/orval.config.ts`:

```ts
import { defineConfig } from "orval"

// Both targets read the same committed artifact. Routes tagged "streaming" are
// SSE: they have no JSON response schema, and generating a react-query mutation
// for one produces a misleading `unknown`-returning hook nobody should call.
const input = {
  target: "../../../server/openapi.json",
  filters: { mode: "exclude" as const, tags: ["streaming"] },
}

export default defineConfig({
  appApi: {
    input,
    output: {
      mode: "tags-split",
      target: "./src/generated/endpoints",
      schemas: "./src/generated/types",
      client: "react-query",
      httpClient: "fetch",
      clean: true,
      prettier: true,
      override: {
        // Without this, the generated types describe an { data, status, headers }
        // envelope while the mutator resolves the parsed body — a disagreement
        // that forces `as unknown as T` at every call site.
        fetch: { includeHttpResponseReturnType: false },
        // A `use`-prefixed mutator name makes orval call it inside each hook,
        // which is what removes the need for a module-level client singleton.
        mutator: {
          path: "./src/use-api-fetch.ts",
          name: "useApiFetch",
        },
        query: {
          useQuery: true,
          useMutation: true,
        },
      },
    },
  },
  appZod: {
    input,
    output: {
      mode: "tags-split",
      target: "./src/generated/zod",
      client: "zod",
      clean: true,
      prettier: true,
    },
  },
})
```

- [ ] **Step 4: Write the post-generation script**

Create `web-app/packages/api-client/scripts/postgen.mjs`:

```js
#!/usr/bin/env node
/**
 * Regenerate the barrel index.ts files under src/generated/.
 *
 * orval's `clean: true` wipes its target directories on every run, so the
 * barrels must be rewritten afterwards. Invoked by the `gen:api` script.
 *
 * - endpoints/ and zod/ use the tags-split layout: one directory per OpenAPI
 *   tag, each holding <tag>.ts. Each tag gets its own index.ts — that is what
 *   the package's "./endpoints/*" and "./zod/*" subpath exports resolve to —
 *   plus one top-level barrel over all tags.
 * - types/ is flat: one .ts per schema, with a single barrel over all of them.
 *
 * One Node file rather than a shell script, because this repository is a
 * template meant to be forked and cloned onto machines without bash.
 */
import { existsSync, readdirSync, writeFileSync } from "node:fs"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"

const packageRoot = join(dirname(fileURLToPath(import.meta.url)), "..")
const generated = join(packageRoot, "src", "generated")

let written = 0

for (const area of ["endpoints", "zod"]) {
  const dir = join(generated, area)
  if (!existsSync(dir)) continue

  const tags = readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort()

  for (const tag of tags) {
    writeFileSync(join(dir, tag, "index.ts"), `export * from "./${tag}"\n`)
    written++
  }

  writeFileSync(join(dir, "index.ts"), tags.map((t) => `export * from "./${t}/${t}"\n`).join(""))
  written++
}

const typesDir = join(generated, "types")
if (existsSync(typesDir)) {
  const modules = readdirSync(typesDir)
    .filter((file) => file.endsWith(".ts") && file !== "index.ts")
    .map((file) => file.slice(0, -3))
    .sort()

  writeFileSync(join(typesDir, "index.ts"), modules.map((m) => `export * from "./${m}"\n`).join(""))
  written++
}

console.log(`postgen: wrote ${written} barrel file(s)`)
```

- [ ] **Step 5: Install and generate**

Run:

```bash
cd web-app && pnpm install && pnpm --filter @app/api-client gen:api
```

Expected: orval reports two targets written, then `postgen: wrote N barrel file(s)`.

- [ ] **Step 6: Verify the generated surface**

Run:

```bash
cd web-app/packages/api-client && \
  ls src/generated/endpoints src/generated/zod && \
  echo "--- system exports ---" && \
  grep -oE "export (const|function) use[A-Za-z]+" src/generated/endpoints/system/system.ts | sort -u && \
  echo "--- stream route excluded ---" && \
  ! grep -rq "useStreamChatMessage" src/generated && echo "OK: no useStreamChatMessage"
```

Expected: `endpoints/` and `zod/` each contain `auth`, `chatbot`, `conversation` and `system` directories (no `streaming`); the system module exports `useGetRoot`, `useGetHealth` and `useGetReadiness`; and `OK: no useStreamChatMessage`.

If the hook name differs from `useGetReadiness`, use the actual name in Task 6 and note the deviation — orval derives it from the `operation_id` set in Task 1, so a mismatch means that id did not land.

- [ ] **Step 7: Confirm no response envelope leaked into the types**

Run:

```bash
cd web-app/packages/api-client && \
  grep -nE "status: *(200|number)|headers: *Headers" src/generated/endpoints/system/system.ts || \
  echo "OK: no response envelope in the generated types"
```

Expected: `OK: no response envelope in the generated types`.

If instead the grep prints lines declaring `{ data: ...; status: 200 }` or a `headers: Headers` member, `includeHttpResponseReturnType: false` did not take effect. Stop and fix the config — do **not** proceed and paper over it with `as unknown as T` at the call sites, which is the failure mode this setting exists to prevent.

- [ ] **Step 8: Type-check the package**

Run: `cd web-app && pnpm --filter @app/api-client exec tsc --noEmit`
Expected: PASS, no output. This is also the check that the zod target compiles against Zod 4 — a failure here means the generated validators use v3 syntax and the orval version needs revisiting before going further.

- [ ] **Step 9: Commit**

```bash
git add web-app/packages/api-client web-app/pnpm-lock.yaml
git commit -m "feat(web): add the @app/api-client package with generated client

Two orval targets over the committed server/openapi.json: react-query
hooks plus flat schema types, and zod validators. Everything orval owns
lives under src/generated/ so clean:true can never reach a hand-written
file; only errors.ts, use-api-fetch.ts and index.ts are hand-written.

The mutator is a hook. A module-level singleton would be shared across
concurrent requests in a Next.js server process and would freeze the
first render's getToken closure; as a hook it reads the current token per
call and needs no provider of its own.

includeHttpResponseReturnType: false makes the generated types resolve
the response body, matching what the mutator returns — without it every
call site needs 'as unknown as T'.

Routes tagged streaming are excluded: SSE has no JSON schema, so a
generated mutation would return unknown.

orval and prettier are pinned exactly. The generated tree is committed,
so a routine install must not rewrite it."
```

---

## Task 6: Wire the apps to the generated client

Applies to **both** `internal-portal` and `supplier-portal`. Every file below exists twice; make the identical change in each.

**Files:**
- Modify: `web-app/apps/*/package.json`
- Modify: `web-app/apps/*/next.config.ts`
- Modify: `web-app/Dockerfile`
- Create: `web-app/apps/*/src/lib/messages.ts`
- Modify: `web-app/apps/*/src/providers/query-provider.tsx`
- Modify: `web-app/apps/*/src/hooks/use-server-status.ts`
- Delete: `web-app/apps/*/src/lib/api/health.ts`

**Interfaces:**
- Consumes: `ApiError` and `useGetReadiness` from Task 5.
- Produces: `messages.toasts.*` — the curated copy the toast mapper reads.

- [ ] **Step 1: Add the dependency and transpile it**

In both `web-app/apps/internal-portal/package.json` and `web-app/apps/supplier-portal/package.json`, add to `dependencies`, keeping alphabetical order among the `@app/*` entries:

```json
    "@app/api-client": "workspace:*",
```

In both `web-app/apps/*/next.config.ts`, extend `transpilePackages`. The packages ship raw TypeScript, so an untranspiled one fails the build:

```ts
  transpilePackages: ["@app/ui", "@app/types", "@app/auth", "@app/api-client"],
```

`@app/types` is removed from this list in Task 7; leave it for now so the build stays green between tasks.

In `web-app/Dockerfile`, add to the deps stage alongside the other manifest copies. The stage copies each workspace `package.json` by name for layer caching, so omitting this one breaks the image build on a lockfile mismatch rather than on a missing file:

```dockerfile
COPY packages/api-client/package.json ./packages/api-client/
```

- [ ] **Step 2: Add the curated toast copy**

Create `web-app/apps/internal-portal/src/lib/messages.ts` and the identical file at `web-app/apps/supplier-portal/src/lib/messages.ts`:

```ts
/**
 * Curated user-facing copy.
 *
 * SECURITY: error toasts map an HTTP status to a string from this file. Never
 * surface ApiError.message or ApiError.body — server payloads can carry stack
 * traces and internal route names.
 */
export const messages = {
  toasts: {
    sessionExpired: "Sessione scaduta. Effettua di nuovo l'accesso.",
    forbidden: "Non hai i permessi per questa operazione.",
    notFound: "Risorsa non trovata.",
    conflictError: "Operazione in conflitto con lo stato attuale.",
    validationError: "Dati non validi.",
    genericError: "Si è verificato un errore. Riprova.",
  },
} as const
```

- [ ] **Step 3: Rewrite the query provider**

Replace the contents of `web-app/apps/internal-portal/src/providers/query-provider.tsx`, and the identical file in `supplier-portal`:

```tsx
"use client"

import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query"
import { ReactQueryDevtools } from "@tanstack/react-query-devtools"
import { useState } from "react"
import { toast } from "sonner"
import { ApiError } from "@app/api-client"
import { isDevelopment } from "../lib/env-helpers"
import { messages } from "../lib/messages"

/**
 * Map an error to a toast.
 *
 * SECURITY: status maps to curated copy. Never surface err.message or the
 * response body — server payloads may contain stack traces or internal route
 * names.
 */
function toastForError(error: unknown): void {
  if (error instanceof ApiError) {
    switch (error.status) {
      case 401:
        toast.error(messages.toasts.sessionExpired)
        return
      case 403:
        toast.error(messages.toasts.forbidden)
        return
      case 404:
        toast.error(messages.toasts.notFound)
        return
      case 409:
        toast.error(messages.toasts.conflictError)
        return
      case 422:
        toast.error(messages.toasts.validationError)
        return
      default:
        if (error.status >= 500) toast.error(messages.toasts.genericError)
        return
    }
  }
  toast.error(messages.toasts.genericError)
}

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({
          onError: (error, query) => {
            // onError fires for background refetches too. A polling query that
            // fails every 30s would otherwise toast every 30s, behind data the
            // user can already see. Only a query that has never resolved
            // toasts, and a query can opt out entirely.
            if (query.meta?.silentError === true) return
            if (query.state.data !== undefined) return
            toastForError(error)
          },
        }),
        // Mutations always toast: the user just acted and is waiting for a result.
        mutationCache: new MutationCache({ onError: toastForError }),
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            gcTime: 5 * 60 * 1000,
            refetchOnWindowFocus: false,
            // Retrying a 4xx burns a request for an answer that will not change.
            retry: (failureCount, error) =>
              failureCount < 1 && !(error instanceof ApiError && error.status < 500),
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      {isDevelopment && <ReactQueryDevtools initialIsOpen={false} />}
    </QueryClientProvider>
  )
}
```

Feature code must not add a generic `onError` toast to an individual mutation — that double-toasts. Per-mutation `onError` is reserved for specific handling: field-level errors, optimistic rollback.

- [ ] **Step 4: Migrate the server-status hook**

Replace the contents of `web-app/apps/internal-portal/src/hooks/use-server-status.ts`, and the identical file in `supplier-portal`:

```ts
"use client"

import { useGetReadiness } from "@app/api-client/endpoints/system"

export function useServerStatus() {
  const { data, isLoading, error } = useGetReadiness({
    query: {
      refetchInterval: 30_000,
      retry: false,
      // The widget renders "degraded" on its own. A global toast every 30
      // seconds during an outage would be noise, so this query opts out.
      meta: { silentError: true },
    },
  })

  return { status: data, isLoading, error }
}
```

- [ ] **Step 5: Delete the hand-written fetcher**

Run:

```bash
cd web-app && rm apps/internal-portal/src/lib/api/health.ts apps/supplier-portal/src/lib/api/health.ts && \
  rmdir apps/internal-portal/src/lib/api apps/supplier-portal/src/lib/api
```

- [ ] **Step 6: Install and type-check**

Run: `cd web-app && pnpm install && pnpm -r exec tsc --noEmit`
Expected: PASS.

`server-status.tsx` reads `status?.components?.agents?.chatbot?.ready`. The generated `agents` type is a `{[key: string]: AgentStatus}` index signature, so that expression still type-checks unchanged. If the type checker disagrees, adjust the widget rather than the schema.

- [ ] **Step 7: Verify the widget in the running app**

Run the stack and confirm the server-status indicator still renders a version and component detail:

```bash
make docker-run-core
```

Open http://localhost:3000, sign in, and check the status indicator in the settings area. Expected: a green dot, a version string, and — in the hover card — API, Database and Chatbot Agent rows.

- [ ] **Step 8: Commit**

```bash
git add web-app/apps web-app/Dockerfile web-app/pnpm-lock.yaml
git commit -m "feat(web): consume the generated client in both portals

useServerStatus now calls the generated useGetReadiness. The hand-written
lib/api/health.ts is deleted from both portals, and with it the last
hand-written API response type in the workspace.

QueryProvider gains centralised error handling: status maps to curated
copy from lib/messages.ts, never to server error text. Query toasts are
gated on first load with a meta opt-out, because onError also fires for
background refetches and the health poll runs every 30 seconds. Retries
skip 4xx. ReactQueryDevtools is retained.

The Dockerfile deps stage copies each workspace manifest by name, so
@app/api-client's is added there too."
```

---

## Task 7: Delete `@app/types`

Only `NavItem` and `HealthResponse` were ever imported. `HealthResponse` is now generated. `Project`, `Supplier`, `Document`, `PurchaseOrder`, `ProjectStatus`, `SupplierRole`, `DocumentStatus` and `DocumentType` have zero importers and describe endpoints that do not exist — under the contract principle they will be generated when those endpoints do.

**Files:**
- Create: `web-app/packages/ui/src/types/nav.ts`
- Modify: `web-app/packages/ui/src/index.ts`
- Modify: `web-app/packages/ui/src/components/layout/app-sidebar.tsx`
- Modify: `web-app/packages/ui/src/components/layout/nav-sidebar.tsx`
- Modify: `web-app/packages/ui/package.json`
- Modify: `web-app/apps/*/src/lib/hub-nav.ts`
- Modify: `web-app/apps/*/package.json`
- Modify: `web-app/apps/*/next.config.ts`
- Modify: `web-app/Dockerfile`
- Delete: `web-app/packages/types/`

**Interfaces:**
- Produces: `NavItem` exported from `@app/ui`.

- [ ] **Step 1: Move `NavItem` into `@app/ui`**

Create `web-app/packages/ui/src/types/nav.ts`:

```ts
import type { LucideIcon } from "lucide-react"

/**
 * Sidebar navigation entry.
 *
 * A UI contract, not an API contract: it is typed by LucideIcon and consumed
 * only by this package's sidebar components and each app's nav configuration.
 */
export type NavItem = {
  title: string
  url: string
  icon?: LucideIcon
  items?: Array<{
    title: string
    url: string
  }>
}
```

Add to `web-app/packages/ui/src/index.ts`, after the `// Utilities` block:

```ts
// Types
export type { NavItem } from "./types/nav"
```

- [ ] **Step 2: Repoint the importers**

In `web-app/packages/ui/src/components/layout/app-sidebar.tsx` and `web-app/packages/ui/src/components/layout/nav-sidebar.tsx`, replace the cross-package import with a local one:

```ts
import type { NavItem } from "../../types/nav"
```

In `web-app/apps/internal-portal/src/lib/hub-nav.ts` and `web-app/apps/supplier-portal/src/lib/hub-nav.ts`:

```ts
import type { NavItem } from "@app/ui"
```

- [ ] **Step 3: Remove the dependency everywhere**

Delete the `"@app/types": "workspace:*",` line from `web-app/packages/ui/package.json`, `web-app/apps/internal-portal/package.json` and `web-app/apps/supplier-portal/package.json`.

In both `web-app/apps/*/next.config.ts`, drop it from the transpile list:

```ts
  transpilePackages: ["@app/ui", "@app/auth", "@app/api-client"],
```

In `web-app/Dockerfile`, delete the line:

```dockerfile
COPY packages/types/package.json ./packages/types/
```

- [ ] **Step 4: Delete the package**

Run:

```bash
cd web-app && rm -rf packages/types && pnpm install
```

- [ ] **Step 5: Verify nothing references it**

Run:

```bash
cd web-app && ! grep -rn "@app/types" apps packages Dockerfile --exclude-dir=node_modules --exclude-dir=.next && echo "OK: no references remain"
```

Expected: `OK: no references remain`.

The two `apps/*/README.md` files also list `@app/types` in a package table — update those lines to name `@app/api-client` instead.

- [ ] **Step 6: Type-check and build**

Run: `cd web-app && pnpm -r exec tsc --noEmit && pnpm build`
Expected: PASS for both.

- [ ] **Step 7: Commit**

```bash
git add -A web-app
git commit -m "refactor(web): delete @app/types

Only NavItem and HealthResponse were ever imported from it.
HealthResponse is now generated from the OpenAPI spec, and NavItem moves
to @app/ui — it is typed by LucideIcon and consumed only by that
package's sidebars and each app's nav config, so it is a UI contract.

The six remaining domain types had zero importers and described
endpoints that do not exist; under the contract principle they will be
generated when those endpoints do. Removing the package also removes the
name collision between it and the generated types directory, which was
the only thing keeping 'never mirror an API schema' a prose rule."
```

---

## Task 8: The drift guard

`server/openapi.json` and the generated tree are committed. Nothing yet catches a route changing without a regeneration, which is the failure that makes the frontend compile against a contract the backend no longer serves.

**Files:**
- Create: `scripts/check-contract.sh`
- Modify: `Makefile`
- Create: `.github/workflows/api-contract.yml`

**Interfaces:**
- Consumes: `make -C server export-openapi` (Task 3) and `pnpm --filter @app/api-client gen:api` (Task 5).
- Produces: `make check-contract`.

- [ ] **Step 1: Write the check script**

Create `scripts/check-contract.sh`:

```bash
#!/usr/bin/env bash
# Verify the committed contract artifacts match the code that produces them.
#
# server/openapi.json and web-app/packages/api-client/src/generated/ are both
# generated and committed. If a route changes and only one of them is
# regenerated, the frontend compiles against a contract the backend no longer
# serves — and nothing fails until runtime. This regenerates both and fails if
# anything moved.
#
# Needs no database, no .env and no secrets: app.openapi() builds the schema
# from registered routes.
set -euo pipefail
cd "$(dirname "$0")/.."

ARTIFACTS=(server/openapi.json web-app/packages/api-client/src/generated)

echo "==> Exporting the OpenAPI spec"
make -C server export-openapi

echo "==> Regenerating the API client"
pnpm --dir web-app --filter @app/api-client gen:api

echo "==> Checking for drift"
# --porcelain covers both modified tracked files and new untracked ones; a plain
# `git diff` would miss a newly generated file for a newly added endpoint.
if [ -n "$(git status --porcelain -- "${ARTIFACTS[@]}")" ]; then
  echo
  echo "FAIL: the committed contract artifacts are stale."
  echo "Run 'make check-contract' locally and commit the result alongside the"
  echo "route change that caused it."
  echo
  git --no-pager status --porcelain -- "${ARTIFACTS[@]}"
  echo
  git --no-pager diff --stat -- "${ARTIFACTS[@]}"
  exit 1
fi

echo "PASS: server/openapi.json and the generated client are up to date."
```

Make it executable:

```bash
chmod +x scripts/check-contract.sh
```

- [ ] **Step 2: Add the Makefile target**

In the root `Makefile`, add `check-contract` to the `.PHONY` list on line 1, then add the target after the `dev-tunnel` block:

```make
# The OpenAPI spec and the generated API client are committed artifacts. This
# regenerates both and fails if the committed versions are stale.
check-contract:
	@./scripts/check-contract.sh
```

And add to the `help:` target, under a new heading after the native dev block:

```make
	@echo ""
	@echo "Contract:"
	@echo "  make check-contract     - Fail if openapi.json or the generated client is stale"
```

- [ ] **Step 3: Verify it passes on a clean tree**

Run: `make check-contract`
Expected: `PASS: server/openapi.json and the generated client are up to date.`

- [ ] **Step 4: Verify it actually catches drift**

Temporarily change a route summary, then confirm the check fails:

```bash
sed -i.bak 's/summary="Get API information"/summary="Get API info"/' server/app/api/system/health.py
make check-contract || echo "EXPECTED FAILURE"
```

Expected: the script prints `FAIL: the committed contract artifacts are stale.` followed by `EXPECTED FAILURE`.

Restore and re-verify:

```bash
mv server/app/api/system/health.py.bak server/app/api/system/health.py
git checkout -- server/openapi.json web-app/packages/api-client/src/generated
make check-contract
```

Expected: PASS.

- [ ] **Step 5: Add the CI workflow**

Create `.github/workflows/api-contract.yml`:

```yaml
name: API contract

on:
  pull_request:
  push:
    branches: [main]

jobs:
  contract:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v5
        with:
          enable-cache: true

      - name: Sync Python dependencies
        working-directory: server
        run: uv sync --frozen

      - uses: pnpm/action-setup@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm
          cache-dependency-path: web-app/pnpm-lock.yaml

      - name: Install workspace dependencies
        working-directory: web-app
        run: pnpm install --frozen-lockfile

      # No database, no .env, no secrets: the spec is built from registered
      # routes via app.openapi().
      - name: Contract artifacts are current
        run: make check-contract

      - name: Contract convention holds
        working-directory: server
        run: APP_ENV=test uv run pytest tests/unit/api/test_openapi_contract.py tests/unit/scripts/test_export_openapi.py -v

      - name: Workspace type-checks
        working-directory: web-app
        run: pnpm -r exec tsc --noEmit
```

- [ ] **Step 6: Commit**

```bash
git add scripts/check-contract.sh Makefile .github/workflows/api-contract.yml
git commit -m "feat(ci): fail the build when the contract artifacts are stale

server/openapi.json and the generated API client are committed. Without a
guard they rot silently: a route changes, one artifact is regenerated and
the other is not, and the frontend compiles against a contract the
backend stopped serving.

scripts/check-contract.sh regenerates both and fails on any difference.
'make check-contract' runs it locally; the workflow runs the same target
on pull requests. One script, two callers.

This is the repository's first CI workflow. It needs no secrets — the
spec export builds the schema from registered routes, with no database
and no .env."
```

---

## Task 9: Correct the portable guide

`docs/api-client-codegen-setup.md` is the transplantable version, written with an `@acme` scope for a fresh template repo. Four of its recommendations were superseded during this workstream. Leaving it uncorrected means the B2C fork inherits the superseded advice.

**Files:**
- Modify: `docs/api-client-codegen-setup.md`

- [ ] **Step 1: Apply the corrections**

Edit `docs/api-client-codegen-setup.md`, keeping the `@acme` scope placeholder throughout:

1. **§9.1 (response envelope)** — delete the Option A / Option B table entirely. Replace with a one-paragraph note that `output.override.fetch.includeHttpResponseReturnType: false` makes the generated types resolve the body, so no cast and no `unwrap<T>()` helper is needed, and show the config snippet.
2. **§6.1 and §6.3 (the mutator and provider)** — replace the module-level singleton, `createApiClient`, and `ApiClientProvider` with the hook mutator: `useApiFetch` sourcing its token from the auth package, `mutator: { path, name: "useApiFetch" }`, and a provider tree with no `ApiClientProvider`. State the trade-off — out-of-React calls need their own path — and keep the singleton described as the alternative for projects that need plain fetcher functions.
3. **§9.4 (provider ordering)** — delete. It only exists because of the singleton.
4. **§2 (repository layout)** — move the generated directories under a single `src/generated/` parent, and update the `exports` map in §4.1 and every import path in §6.5, §6.6, §7 and §8 to match (`endpoints/`, `types/`, `zod/`).
5. **§5 (post-processing)** — keep the barrel generation, rewritten as a single Node script. Move the array-param serializer patch out of the script and into §9.2 as a hazard to add when the first array query parameter appears, with the regression test it prescribes.
6. **§3 (backend requirements)** — add the two rules this repo needed and the guide lacked: streaming routes take their own tag and are excluded via `input.filters`; server-to-server routes declare `include_in_schema=False`. Note that `operation_id` casing is a project convention — this repo uses camelCase — and that `Dict[str, Any]` is not a response model.
7. **§6.4 (QueryProvider)** — add the first-load gating and the `meta` opt-out for the query cache, the 4xx retry predicate, and a note to keep the devtools.
8. **§4.1 (package.json)** — pin `orval` and `prettier` exactly and say why, and add `prettier` as a devDependency.
9. **§10 (rebuild checklist)** — update every item touched above, and add a line for the `check-contract` script and CI job.

Add a note under the Status header recording that the guide was reconciled against a live implementation, and pointing at the WS5 spec:

```markdown
**Revised:** 2026-09-01, reconciled against the implementation in
`docs/superpowers/specs/2026-09-01-ws5-api-client-codegen-design.md`. Four of
the original recommendations were superseded; the rationale for each is
recorded there.
```

- [ ] **Step 2: Verify no superseded advice survives**

Run:

```bash
grep -n "createApiClient\|ApiClientProvider\|custom-instance\|unwrap<\|as unknown as" docs/api-client-codegen-setup.md
```

Expected: hits only in passages that explicitly describe the singleton as the alternative approach, never as the recommendation.

- [ ] **Step 3: Update the workstream tracker**

In `docs/superpowers/specs/2026-08-24-template-hardening-design.md`, change the WS5 row to complete and name the plan:

```markdown
| 5 | Orval codegen | ✅ Complete | `plans/2026-09-01-ws5-api-client-codegen.md` | — |
```

- [ ] **Step 4: Commit**

```bash
git add docs/api-client-codegen-setup.md docs/superpowers/specs/2026-08-24-template-hardening-design.md
git commit -m "docs: reconcile the codegen guide with the WS5 implementation

Four recommendations were superseded while implementing WS5: the
response-envelope workaround (a config flag removes the problem), the
singleton mutator and its provider (a hook mutator removes both), the
flat package layout (a generated/ parent makes clean:true safe), and the
array-param patch (kept as a documented hazard, not shipped code).

The guide keeps the @acme placeholder scope so it stays transplantable
into the B2C fork."
```

---

## Verification

After all nine tasks, from the repo root:

```bash
make check-contract
cd server && APP_ENV=test uv run pytest tests/ -v
cd ../web-app && pnpm -r exec tsc --noEmit && pnpm build
cd .. && make docker-build-web && make docker-build-api
```

All must pass. Then confirm the acceptance criteria from the spec:

- [ ] `git diff` is clean after a regeneration.
- [ ] No `useStreamChatMessage` anywhere under `web-app/packages/api-client/src/generated/`.
- [ ] `grep -rn "@app/types" web-app --exclude-dir=node_modules --exclude-dir=.next` returns nothing.
- [ ] No hand-written API request or response type remains under `web-app/`.
- [ ] The server-status widget renders from `useGetReadiness` in both portals.
