# Coding Conventions

**Analysis Date:** 2026-02-26

## Naming Patterns

**Files:**
- **Python**: `snake_case.py` - Used throughout backend (`app/core/config.py`, `app/database/engine.py`, `app/services/transaction/service.py`)
- **TypeScript/React**: `kebab-case.tsx` for components and routes (`app-sidebar.tsx`, `user-panel.tsx`), `camelCase.ts` for utilities (`utils.ts`)
- **Routes**: File-based routing (Next.js) with directory grouping for layout separation (`(app)/`, `(auth)/`)

**Functions:**
- **Python**: `snake_case()` consistently used (`async def initialize_database_engine()`, `async def get_spending_summary()`, `async def test_database_connection()`)
- **TypeScript**: `camelCase()` for functions and hooks (`useSidebar()`, `useIsMobile()`, `handleSignOutClick()`)
- **Component Exports**: `PascalCase` for component names (`export function UserDetailsPanel()`, `export default function Page()`)

**Variables:**
- **Python**: `SCREAMING_SNAKE_CASE` for constants (`SIDEBAR_COOKIE_NAME`, `SIDEBAR_COOKIE_MAX_AGE`, `SIDEBAR_WIDTH`)
- **TypeScript**: `camelCase` for variables, `UPPER_CASE` for constants (`const SIDEBAR_COOKIE_NAME = "sidebar_state"`)
- **Types/Interfaces**: `PascalCase` (`SidebarContextProps`, `Environment`, `DatabaseSettings`)

**Types:**
- **Python**: Class-based (`class Environment(str, Enum)`, `class Settings(BaseSettings)`)
- **TypeScript**: `type` keyword for simple types (`type SidebarContextProps = { ... }`)
- **Enums**: `PascalCase` names with `UPPER_CASE` members (`Environment.PRODUCTION`, `CategoryEnum.SHOPPING`)

## Code Style

**Formatting:**
- **Python**: Black formatter with 119 character line length (`tool.black` in `pyproject.toml`)
- **TypeScript/React**: No explicit formatter config found, but code follows standard conventions with consistent indentation
- **Tab/Space**: Python uses spaces (4-space indentation), TypeScript uses tabs (based on sidebar.tsx)

**Linting:**
- **Python**:
  - Ruff with `select = ["E", "F", "B", "ERA", "D"]` (errors, warnings, bugbear, eradicate, docstrings)
  - Flake8 with docstring convention "all" (`tool.flake8` in `pyproject.toml`)
  - Ignore rules: E501 (line length), F401 (unused imports), D203 (blank line before docstring)
  - Max complexity (radon): 10

- **TypeScript/React**:
  - ESLint using `eslint-config-next/core-web-vitals` and `eslint-config-next/typescript` (`web-app/eslint.config.mjs`)
  - Flat config format (ESLint v9+)
  - Ignores: `.next/`, `out/`, `build/`, `next-env.d.ts`

## Import Organization

**Order:**
1. Standard library imports (`import os`, `import asyncio`)
2. Third-party imports (`import pytest`, `import fastapi`, `from sqlalchemy import`)
3. Relative/app imports (`from app.core.config import`, `from app.database.engine import`)

**Path Aliases:**
- **TypeScript**: `@/*` maps to `./src/*` (defined in `tsconfig.json`) - used throughout (`@/components/ui/sidebar`, `@/hooks/use-mobile`, `@/lib/utils`)
- **Python**: No path aliases used; absolute imports from `app` root

**Imports Style:**
- Python: Multi-line imports use vertical hanging indent with grid wrap:
  ```python
  from app.models.transaction import (
      CategoryEnum,
      Transaction,
  )
  ```
- TypeScript: Named imports grouped logically, often spanning multiple lines with proper formatting

## Error Handling

**Patterns:**
- **Python**: Custom exception hierarchy with `ServiceError` base class
  - `app/exceptions/base.py` defines base `ServiceError` with `error_code`, `status_code`, `message`, `context` attributes
  - Service-specific exceptions in `app/services/*/exceptions.py` (e.g., `app/services/transaction/exceptions.py`)
  - Global exception handler in `app/exceptions/handlers.py` catches `ServiceError`, `RequestValidationError`, and generic `Exception`
  - Context variables passed through exception: `exc.context` dict for additional error details

- **TypeScript**: No explicit error handling patterns found in current codebase; relies on framework defaults and async/await

**Error Response Format:**
```python
# From ErrorResponse schema
{
    "error": "error_code",
    "message": "Human readable message",
    "correlation_id": "unique-id-from-context",
    "details": {...}  # Optional context dict
}
```

## Logging

**Framework:**
- **Python**: `structlog` with structured logging (observed in `app/core/logging.py`)
- **TypeScript**: `console` (no centralized logging framework observed)

**Patterns:**
- **Python**:
  - Structured logging with event name as first arg: `logger.info("event_name", key=value, ...)`
  - Exception logging uses `logger.exception()` to capture full traceback with context
  - Log levels match HTTP status codes: `logger.exception()` for 5xx, `logger.warning()` for 4xx, `logger.info()` for others
  - Context includes: `correlation_id`, `error_type`, `status_code`, `endpoint`, `method`
  - Log directory: `Path("logs")` (configurable via `LOG_DIR`)
  - Format: JSON or console (configurable via `LOG_FORMAT`)

- **TypeScript**: Not extensively used in frontend; components log directly with `console.log()` if needed

## Comments

**When to Comment:**
- **Python**: Use docstrings extensively with Google convention
  - Module-level docstrings describe purpose and behavior
  - Function/method docstrings include Args, Returns, Raises sections
  - Inline comments for non-obvious logic (e.g., "This sets the cookie to keep the sidebar state")
  - Multi-line comments above code sections (e.g., "# ── Analytics transaction fixtures ────")

- **TypeScript**: Inline comments for complex logic, minimal docstrings

**JSDoc/TSDoc:**
- Minimal in TypeScript frontend code
- Python uses Google-style docstrings with full Args/Returns

## Function Design

**Size:**
- **Python**: Functions average 10-40 lines
- Small focused functions like `get_environment()` (10 lines)
- Larger orchestration functions like `service_exception_handler()` (40 lines) acceptable for complex logic

**Parameters:**
- **Python**:
  - Positional-only for core data: `async def initialize_database_engine() -> AsyncEngine`
  - Keyword-only for config: `pool_pre_ping=True, pool_size=..., max_overflow=...`
  - Defaults for optional parameters: `start_date: Optional[date] = None`

- **TypeScript**:
  - Object destructuring: `export function cn(...inputs: ClassValue[])`
  - Optional props: `open?: boolean`, `onOpenChange?: (open: boolean) => void`
  - Default parameters: `defaultOpen = true`

**Return Values:**
- **Python**: Type hints required (`-> AsyncEngine`, `-> bool`, `-> Dict[str, Any]`)
- **TypeScript**: Type hints for React props and functions
- No implicit returns (explicit `return` statements)

## Module Design

**Exports:**
- **Python**:
  - `from app.models.user import User` pattern - direct imports from modules
  - `__all__` not consistently used
  - Explicit imports in `__init__.py` for package exports (observed in `app/agents/insights/__init__.py`)

- **TypeScript**:
  - Named exports: `export function UserDetailsPanel()`, `export default function Page()`
  - Mixed default and named exports
  - Path alias imports: `from "@/components/ui/sidebar"`

**Barrel Files:**
- **Python**: Not extensively used; direct module imports preferred
- **TypeScript**: UI component directories have barrel exports (inferred from import patterns)

## Configuration & Environment

**Settings Pattern (Python):**
- Pydantic `BaseSettings` with `SettingsConfigDict` for environment loading
- Nested settings classes organized by domain: `DatabaseSettings`, `LLMSettings`, `AuthSettings`, `LoggingSettings`
- Environment-specific `.env.{environment}` files (`.env.development`, `.env.test`)
- `case_sensitive=False` for env var matching
- `SecretStr` type for sensitive values
- Field validators for derived properties: `@field_validator` decorator

**Configuration Files:**
- `.env.development`, `.env.test` - environment-specific configs
- `pyproject.toml` - Python tool configuration (Black, Isort, Ruff, Pytest)
- `tsconfig.json` - TypeScript configuration with path aliases
- `eslint.config.mjs` - ESLint v9 flat config

---

*Convention analysis: 2026-02-26*
