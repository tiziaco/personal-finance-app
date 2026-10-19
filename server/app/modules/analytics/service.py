"""Analytics service: load the user's history once, then run a calculation over it."""

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.domain.period import usable_rows
from app.modules.analytics.history import AnalyticsHistory
from app.modules.analytics.schemas import (
    AnomaliesResponse,
    BehaviourResponse,
    CategoryBreakdownResponse,
    DashboardResponse,
    DateRange,
    MerchantBreakdownResponse,
    RecurringResponse,
    SpendingResponse,
)
from app.modules.transaction import MAX_DATE, MIN_DATE, transaction_service


def _today() -> dt.date:
    """Today's date in UTC; route tests pin it by monkeypatching this."""
    return dt.datetime.now(dt.UTC).date()


class AnalyticsService:
    """Every analysis over one user's active transactions. A caller that needs several windows takes one `history()` and calls it."""

    @staticmethod
    async def history(session: AsyncSession, user_id: uuid.UUID) -> AnalyticsHistory:
        """The user's usable rows and today, loaded once; run any analysis over any window on it."""
        today = _today()
        rows = usable_rows(await transaction_service.list_for_analysis(session, user_id, MIN_DATE, MAX_DATE), today)
        return AnalyticsHistory(rows=tuple(rows), today=today)

    @staticmethod
    async def dashboard(session: AsyncSession, user_id: uuid.UUID) -> DashboardResponse:
        """The home dashboard figures."""
        return (await AnalyticsService.history(session, user_id)).dashboard()

    @staticmethod
    async def spending(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> SpendingResponse:
        """Income, expenses and net over the period, and the current month so far."""
        return (await AnalyticsService.history(session, user_id)).spending(date_range)

    @staticmethod
    async def categories(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, top_n: int
    ) -> CategoryBreakdownResponse:
        """Spend by category over the range."""
        return (await AnalyticsService.history(session, user_id)).categories(date_range, top_n)

    @staticmethod
    async def merchants(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, top_n: int
    ) -> MerchantBreakdownResponse:
        """Spend by merchant over the period."""
        return (await AnalyticsService.history(session, user_id)).merchants(date_range, top_n)

    @staticmethod
    async def recurring(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> RecurringResponse:
        """Recurring spend over the period."""
        return (await AnalyticsService.history(session, user_id)).recurring(date_range)

    @staticmethod
    async def behaviour(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> BehaviourResponse:
        """Spending patterns over the range."""
        return (await AnalyticsService.history(session, user_id)).behaviour(date_range)

    @staticmethod
    async def anomalies(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, std_threshold: float, window_days: int
    ) -> AnomaliesResponse:
        """Outliers and category spikes over the period."""
        return (await AnalyticsService.history(session, user_id)).anomalies(date_range, std_threshold, window_days)


analytics_service = AnalyticsService()
