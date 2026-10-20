"""The finance tools against a seeded database: one history per turn, the context's user only, the routes' figures."""

import asyncio
import datetime as dt
from contextlib import asynccontextmanager
from unittest.mock import patch

import pytest

from app.agents.chatbot.toolkit import ToolArgumentError, TurnContext
from app.modules.analytics import service as analytics_service_module
from app.modules.conversation.finance import service
from app.modules.conversation.finance.service import NO_TRANSACTIONS, finance_toolkit, preamble

pytestmark = pytest.mark.integration

TODAY = dt.date(2026, 10, 16)
TOOLS = {tool.name: tool for tool in finance_toolkit().tools}


@pytest.fixture(autouse=True)
def today(monkeypatch):
    """Pin analytics' today, so a period resolves the same whenever the suite runs."""
    monkeypatch.setattr(analytics_service_module, "_today", lambda: TODAY)
    return TODAY


@pytest.fixture
def turn(db_session):
    """A turn's context for a user; its sessions are the test's, so they see the seeded rows."""

    @asynccontextmanager
    async def session():
        yield db_session

    def make(user) -> TurnContext:
        return TurnContext(user_id=user.id, session_factory=session)

    return make


async def run(name: str, ctx: TurnContext, **args):
    tool = TOOLS[name]
    return await tool.run(tool.args_schema.model_validate(args), ctx)


async def seed(add, user, merchant: str = "Lidl"):
    await add(user, "2026-07-03", "2000.00", category="salary", merchant="Employer")
    await add(user, "2026-08-25", "2000.00", category="salary", merchant="Employer")
    await add(user, "2026-08-05", "-420.00", merchant=merchant)
    await add(user, "2026-09-05", "-180.50", merchant=merchant)
    await add(user, "2026-09-10", "-900.00", category="household_utilities", merchant="Landlord", recurring=True)
    await add(user, "2026-09-25", "2100.00", category="salary", merchant="Employer")
    await add(user, "2026-10-02", "-30.00", merchant=merchant)


async def test_history_loads_once_per_turn(test_user, add, turn):
    await seed(add, test_user)
    ctx = turn(test_user)
    original = service.analytics_service.history

    with patch.object(service.analytics_service, "history", side_effect=original) as load:
        await preamble(ctx)
        await asyncio.gather(run("spending_overview", ctx, months=3), run("category_breakdown", ctx, months=1))
        await run("top_merchants", ctx, months=3)

    assert load.call_count == 1


async def test_tools_read_only_the_context_user(test_user, other_user, add, turn):
    await seed(add, test_user, merchant="Lidl")
    await seed(add, other_user, merchant="Secret Boutique")
    await add(other_user, "2026-09-07", "-9999.00", merchant="Secret Boutique")

    outcomes = [
        await run(name, turn(test_user), date_from="2026-07-01", date_to="2026-10-16")
        for name in ("spending_overview", "top_merchants", "recurring_costs", "unusual_spending")
    ]

    for outcome in outcomes:
        assert "Secret Boutique" not in outcome.content
        assert "9999" not in outcome.content
        assert "Secret Boutique" not in outcome.display.model_dump_json()
    assert "Lidl" in outcomes[1].content


async def test_figures_match_the_analytics_route(authenticated_client, test_user, add, turn):
    await seed(add, test_user)

    for months in (1, 3):
        route = (await authenticated_client.get("/api/v1/analytics/spending", params={"months": months})).json()
        outcome = await run("spending_overview", turn(test_user), months=months)

        spent = next(item for item in outcome.display.summary if item.label == "spent")
        income = next(item for item in outcome.display.summary if item.label == "income")
        assert spent.value == float(route["total_expenses"])
        assert income.value == float(route["total_income"])
        assert f"expenses {route['total_expenses']} EUR" in outcome.content
        assert f"savings rate {route['savings_rate_pct']:.1f}%" in outcome.content


async def test_category_figures_match_the_analytics_route(authenticated_client, test_user, add, turn):
    await seed(add, test_user)

    route = (await authenticated_client.get("/api/v1/analytics/categories", params={"months": 3, "top_n": 50})).json()
    outcome = await run("category_breakdown", turn(test_user), months=3)

    assert outcome.content.startswith("Jul – Sep 2026")
    assert [r["total"] for r in outcome.display.table.rows] == [float(c["total"]) for c in route["top_categories"]]


async def test_preamble_without_transactions_says_so(test_user, other_user, add, turn):
    await seed(add, other_user)  # another user's data is not this user's

    assert await preamble(turn(test_user)) == NO_TRANSACTIONS
    with pytest.raises(ToolArgumentError, match=NO_TRANSACTIONS):
        await run("category_breakdown", turn(test_user), months=1)


async def test_preamble_with_transactions(test_user, add, turn):
    await seed(add, test_user)

    text = await preamble(turn(test_user))

    assert text == "Last finished month: September 2026; data covers July 2026 to October 2026."


async def test_a_period_before_the_data_names_the_span(test_user, add, turn):
    await seed(add, test_user)

    with pytest.raises(ToolArgumentError, match="data covers July 2026 to October 2026"):
        await run("spending_overview", turn(test_user), date_from="2019-01-01", date_to="2019-12-31")
