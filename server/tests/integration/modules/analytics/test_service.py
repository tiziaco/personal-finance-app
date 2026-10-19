"""AnalyticsService.history: one load of the user's rows serves every analysis."""

import datetime as dt

import pytest

from app.modules.analytics import DateRange, analytics_service
from app.modules.analytics import service as analytics_service_module
from app.modules.transaction import transaction_service

pytestmark = pytest.mark.integration

TODAY = dt.date(2026, 10, 16)


async def test_history_loads_rows_once(db_session, test_user, add, monkeypatch):
    monkeypatch.setattr(analytics_service_module, "_today", lambda: TODAY)
    await add(test_user, "2026-09-05", "-200.00")
    loads = []
    original = transaction_service.list_for_analysis

    async def counting(*args, **kwargs):
        loads.append(args)
        return await original(*args, **kwargs)

    monkeypatch.setattr(transaction_service, "list_for_analysis", counting)

    history = await analytics_service.history(db_session, test_user.id)
    history.spending(DateRange(months=3))
    history.categories(DateRange(months=3), 5)
    history.anomalies(DateRange(months=3), 2.0, 90)
    history.dashboard()

    assert len(loads) == 1
