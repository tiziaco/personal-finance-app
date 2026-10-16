"""Analytics service: load the user's rows, run a calculation, shape the response."""

import datetime as dt
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.domain.anomalies import find_anomalies
from app.modules.analytics.domain.behaviour import behaviour_analysis
from app.modules.analytics.domain.categories import category_breakdown
from app.modules.analytics.domain.dashboard import build_dashboard
from app.modules.analytics.domain.merchants import merchant_breakdown
from app.modules.analytics.domain.period import Period, resolve_period, usable_rows
from app.modules.analytics.domain.recurring import recurring_analysis
from app.modules.analytics.domain.spending import spending_summary
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
from app.modules.transaction import MAX_DATE, MIN_DATE, AnalysisRow, transaction_service


async def _rows(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> list[AnalysisRow]:
    """The user's active rows inside the range; an omitted bound stops at MIN_DATE or MAX_DATE.

    Without that stop, one row dated 9999 would stretch every month and day series to the year 9999.
    """
    return await transaction_service.list_for_analysis(
        session, user_id, date_range.date_from or MIN_DATE, date_range.date_to or MAX_DATE
    )


def _today() -> dt.date:
    """Today's date in UTC; route tests pin it by monkeypatching this."""
    return dt.datetime.now(dt.UTC).date()


async def _context(
    session: AsyncSession, user_id: uuid.UUID, date_range: DateRange
) -> tuple[list[AnalysisRow], Optional[Period], dt.date]:
    """The user's usable rows, the period the range resolves to, and today (spec §3.4).

    Every row is loaded, not only the period's: months=N, the month before the period and the rolling
    average need rows outside it.
    """
    today = _today()
    rows = usable_rows(await transaction_service.list_for_analysis(session, user_id, MIN_DATE, MAX_DATE), today)
    period = resolve_period(
        rows, today, date_from=date_range.date_from, date_to=date_range.date_to, months=date_range.months
    )
    return rows, period, today


class AnalyticsService:
    """Every analysis over one user's active transactions. Steps 6 and 7 call these directly."""

    @staticmethod
    async def dashboard(session: AsyncSession, user_id: uuid.UUID) -> DashboardResponse:
        """The home dashboard figures."""
        rows = await _rows(session, user_id, DateRange())
        return DashboardResponse.model_validate(
            build_dashboard(rows, today=dt.datetime.now(dt.UTC).date()), from_attributes=True
        )

    @staticmethod
    async def spending(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> SpendingResponse:
        """Income, expenses and net over the period, and the current month so far."""
        rows, period, today = await _context(session, user_id, date_range)
        return SpendingResponse.model_validate(spending_summary(rows, period, today=today))

    @staticmethod
    async def categories(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, top_n: int
    ) -> CategoryBreakdownResponse:
        """Spend by category over the range."""
        rows, period, today = await _context(session, user_id, date_range)
        return CategoryBreakdownResponse.model_validate(category_breakdown(rows, period, top_n, today=today))

    @staticmethod
    async def merchants(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, top_n: int
    ) -> MerchantBreakdownResponse:
        """Spend by merchant over the period."""
        rows, period, _ = await _context(session, user_id, date_range)
        return MerchantBreakdownResponse.model_validate(merchant_breakdown(rows, period, top_n))

    @staticmethod
    async def recurring(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> RecurringResponse:
        """Recurring spend over the period."""
        rows, period, _ = await _context(session, user_id, date_range)
        return RecurringResponse.model_validate(recurring_analysis(rows, period))

    @staticmethod
    async def behaviour(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> BehaviourResponse:
        """Spending patterns over the range."""
        rows, period, _ = await _context(session, user_id, date_range)
        return BehaviourResponse.model_validate(behaviour_analysis(rows, period))

    @staticmethod
    async def anomalies(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, std_threshold: float, window_days: int
    ) -> AnomaliesResponse:
        """Outliers and category spikes over the period."""
        rows, period, _ = await _context(session, user_id, date_range)
        return AnomaliesResponse.model_validate(find_anomalies(rows, period, std_threshold, window_days))


analytics_service = AnalyticsService()
