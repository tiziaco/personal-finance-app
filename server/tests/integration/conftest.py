"""Integration test fixtures — real DB, mocked external services, short-circuit auth."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock

from app.api.dependencies.agent import get_chatbot_agent
from app.api.dependencies.auth import get_current_user
from app.main import app
from app.models.user import User
from app.schemas.chat import Message

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def test_user(db_session):
    """Create a test user in the database, rolled back after each test."""
    user = User(
        clerk_id="user_test_integration_abc123",
        email="integration@example.com",
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def authenticated_client(client, test_user):
    """HTTP client with get_current_user overridden to return test_user directly.

    Bypasses JWT verification and JIT provisioning entirely.
    The DB session is still active — routes can still write to DB.
    """
    app.dependency_overrides[get_current_user] = lambda: test_user
    yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def mock_agent():
    """Mock ChatbotAgent with pre-configured async method stubs."""
    agent = MagicMock()
    agent.get_response = AsyncMock(return_value=[
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
    ])
    agent.get_chat_history = AsyncMock(return_value=[
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi there!"),
    ])
    agent.clear_chat_history = AsyncMock(return_value=None)
    agent.llm_service.get_llm.return_value.get_name.return_value = "gpt-5-mini"
    agent.is_ready.return_value = True
    return agent


@pytest_asyncio.fixture
async def authenticated_client_with_agent(authenticated_client, mock_agent):
    """HTTP client with both auth and chatbot agent overridden."""
    app.dependency_overrides[get_chatbot_agent] = lambda: mock_agent
    yield authenticated_client
    app.dependency_overrides.pop(get_chatbot_agent, None)


# ── Analytics transaction fixtures ────────────────────────────────────────────

import polars as pl
from decimal import Decimal
from datetime import datetime

from app.models.transaction import CategoryEnum, Transaction


def _load_transactions_from_csv(path: str, test_user, db_session):
    """Helper: read CSV, override user_id with test_user.id, return Transaction list."""
    df = pl.read_csv(path)
    transactions = []
    for row in df.iter_rows(named=True):
        raw_date = row["date"]
        parsed_date = (
            datetime.strptime(raw_date, "%Y-%m-%d") if isinstance(raw_date, str) else raw_date
        )
        t = Transaction(
            user_id=test_user.id,
            date=parsed_date,
            merchant=row["merchant"],
            amount=Decimal(str(row["amount"])),
            description=row.get("description") or None,
            original_category=row.get("original_category") or None,
            category=CategoryEnum(row["category"]),
            confidence_score=float(row["confidence_score"]),
            is_recurring=str(row["is_recurring"]).lower() == "true",
        )
        transactions.append(t)
    return transactions


@pytest_asyncio.fixture
async def transactions_single(db_session, test_user):
    """1 transaction inline — tests division-by-zero and empty-trend edge cases."""
    t = Transaction(
        user_id=test_user.id,
        date=datetime(2025, 6, 15),
        merchant="ACME Corp",
        amount=Decimal("-75.00"),
        category=CategoryEnum.SHOPPING,
        confidence_score=1.0,
        is_recurring=False,
    )
    db_session.add(t)
    await db_session.flush()


@pytest_asyncio.fixture
async def transactions_10(db_session, test_user):
    """10 transactions from test_transactions_10.csv (same month)."""
    for t in _load_transactions_from_csv(
        "tests/data/test_transactions_10.csv", test_user, db_session
    ):
        db_session.add(t)
    await db_session.flush()


@pytest_asyncio.fixture
async def transactions_2_months(db_session, test_user):
    """~90 transactions from test_transactions_2_months.csv (2 continuous months)."""
    for t in _load_transactions_from_csv(
        "tests/data/test_transactions_2_months.csv", test_user, db_session
    ):
        db_session.add(t)
    await db_session.flush()


@pytest_asyncio.fixture
async def transactions_400(db_session, test_user):
    """~400 transactions from test_transactions_400.csv (3 years)."""
    for t in _load_transactions_from_csv(
        "tests/data/test_transactions_400.csv", test_user, db_session
    ):
        db_session.add(t)
    await db_session.flush()
