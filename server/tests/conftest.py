"""Shared test fixtures and configuration.

This module provides pytest fixtures for testing the FastAPI application,
including the test database and HTTP clients.
"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel
from testcontainers.community.postgres import PostgresContainer

# Set test environment and load .env.test into os.environ BEFORE importing app.
# This is required because nested pydantic-settings models (DatabaseSettings, etc.)
# have their own SettingsConfigDict without env_file, so they only read os.environ.
os.environ["APP_ENV"] = "test"

from dotenv import load_dotenv

load_dotenv(".env.test", override=True)

from app.core.config import settings
from app.core.limiter import limiter
from app.database.dependencies import get_db_session
from app.main import app

# pytest.ini runs every async fixture and test on one session-scoped loop, so the
# pool of the session-scoped test_engine is usable in every test.


# ============================================================================
# Database Fixtures
# ============================================================================


@pytest.fixture(scope="session")
def postgres_container():
    """Run a throwaway PostgreSQL for the test session.

    Session-scoped and lazy: only `test_engine` depends on it, and only
    integration tests reach `test_engine` (via `db_session`), so a unit-test
    run never starts a container.

    Uses the same pgvector image as dev/prod for parity — no model declares a
    vector column today, so the extension is not required, but the image is
    already present locally and keeps the versions aligned.

    Requires a running Docker daemon. The container gets an ephemeral host
    port, so it can never collide with the dev database.
    """
    with PostgresContainer("pgvector/pgvector:pg18", driver="asyncpg") as postgres:
        yield postgres


@pytest.fixture(scope="session")
def test_database_url(postgres_container) -> str:
    """Get the connection URL of the throwaway test database.

    Returns:
        str: PostgreSQL connection URL for testing
    """
    return postgres_container.get_connection_url()


@pytest_asyncio.fixture(scope="session")
async def test_engine(test_database_url: str):
    """Create async test database engine.

    Creates all tables at session start and drops them at session end. The
    database lives in a throwaway container (see `postgres_container`), so it
    starts empty every run and cannot touch development data.

    Args:
        test_database_url: Database connection URL

    Yields:
        AsyncEngine: SQLAlchemy async engine for testing
    """
    engine = create_async_engine(
        test_database_url,
        echo=False,  # Set to True for SQL query debugging
        future=True,
        pool_pre_ping=True,  # Verify connections before using
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    # Drop all tables after tests
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)

    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create a new database session for each test.

    Uses an outer transaction on the raw connection that is always rolled back,
    while the session operates with savepoints. This means tests can freely call
    session.add(), session.commit(), session.refresh() — all writes are undone
    after the test finishes.

    Args:
        test_engine: Async database engine

    Yields:
        AsyncSession: Database session for testing
    """
    async with test_engine.connect() as conn:
        # Start an outer transaction — will be rolled back after the test
        trans = await conn.begin()

        # Session uses savepoints so commit() doesn't touch the outer transaction
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        yield session

        await session.close()
        await trans.rollback()


# ============================================================================
# FastAPI Client Fixtures
# ============================================================================


@pytest_asyncio.fixture
async def client(test_engine, db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP test client with database session override.

    Injects the test engine into app.state so endpoints that read
    request.app.state.engine (e.g. /health) work without the lifespan.
    Database operations are automatically rolled back after each test.

    Args:
        test_engine: Session-scoped async engine (sets app.state.engine)
        db_session: Test database session (overrides the DB dependency)

    Yields:
        AsyncClient: HTTPX async client for testing
    """
    app.state.engine = test_engine

    async def override_get_session():
        yield db_session

    app.dependency_overrides[get_db_session] = override_get_session

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def unauthenticated_client(test_engine) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP test client without authentication.

    Injects the test engine into app.state so public endpoints that read
    request.app.state.engine (e.g. /health) work without the lifespan.

    Args:
        test_engine: Session-scoped async engine (sets app.state.engine)

    Yields:
        AsyncClient: HTTPX async client without auth headers
    """
    app.state.engine = test_engine

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ============================================================================
# Utility Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def reset_app_state():
    """Reset application state before each test.

    This ensures tests don't interfere with each other through shared state.
    Runs automatically before every test.
    """
    # Clear any dependency overrides
    app.dependency_overrides.clear()

    yield

    # Cleanup after test
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Give the app its limiter and zero its counts before each test.

    No lifespan runs under test, so nothing sets app.state.limiter: without it a
    tripped limit answers 500 instead of 429. Counts live in the process-wide
    limiter, so they would also leak from one test into the next.
    """
    app.state.limiter = limiter
    limiter.reset()


# ============================================================================
# Markers Configuration
# ============================================================================


def pytest_configure(config):
    """Configure pytest markers.

    This allows us to mark tests with custom markers like:
    - @pytest.mark.unit - Fast unit tests
    - @pytest.mark.integration - Integration tests with database
    - @pytest.mark.slow - Slow tests (e.g., LLM calls)
    - @pytest.mark.asyncio - Async tests (provided by pytest-asyncio)
    """
    config.addinivalue_line("markers", "unit: Unit tests that don't require database or external services")
    config.addinivalue_line("markers", "integration: Integration tests that use database or external services")
    config.addinivalue_line("markers", "slow: Slow tests that make external API calls")
    config.addinivalue_line("markers", "asyncio: Async tests using pytest-asyncio")
