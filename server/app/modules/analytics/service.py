"""Analytics service: load the user's rows, run a calculation, shape the response."""

import datetime as dt
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.analytics.domain.anomalies import find_anomalies
from app.modules.analytics.domain.behaviour import behaviour_analysis
from app.modules.analytics.domain.categories import category_breakdown
from app.modules.analytics.domain.dashboard import build_dashboard
from app.modules.analytics.domain.merchants import merchant_breakdown
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
from app.modules.transaction import AnalysisRow, transaction_service


async def _rows(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> list[AnalysisRow]:
    """The user's active rows inside the range."""
    return await transaction_service.list_for_analysis(session, user_id, date_range.date_from, date_range.date_to)


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
        """Income, expenses and net over the range."""
        rows = await _rows(session, user_id, date_range)
        result = spending_summary(rows, date_range.date_from, date_range.date_to)
        return SpendingResponse.model_validate(result, from_attributes=True)

    @staticmethod
    async def categories(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, top_n: int
    ) -> CategoryBreakdownResponse:
        """Spend by category over the range."""
        rows = await _rows(session, user_id, date_range)
        result = category_breakdown(rows, top_n, date_range.date_from, date_range.date_to)
        return CategoryBreakdownResponse.model_validate(result, from_attributes=True)

    @staticmethod
    async def merchants(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, top_n: int
    ) -> MerchantBreakdownResponse:
        """Spend by merchant over the range."""
        rows = await _rows(session, user_id, date_range)
        return MerchantBreakdownResponse.model_validate(merchant_breakdown(rows, top_n), from_attributes=True)

    @staticmethod
    async def recurring(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> RecurringResponse:
        """Recurring spend over the range."""
        rows = await _rows(session, user_id, date_range)
        return RecurringResponse.model_validate(recurring_analysis(rows), from_attributes=True)

    @staticmethod
    async def behaviour(session: AsyncSession, user_id: uuid.UUID, date_range: DateRange) -> BehaviourResponse:
        """Spending patterns over the range."""
        rows = await _rows(session, user_id, date_range)
        result = behaviour_analysis(rows, date_range.date_from, date_range.date_to)
        return BehaviourResponse.model_validate(result, from_attributes=True)

    @staticmethod
    async def anomalies(
        session: AsyncSession, user_id: uuid.UUID, date_range: DateRange, std_threshold: float, window_days: int
    ) -> AnomaliesResponse:
        """Outliers and category spikes over the range."""
        rows = await _rows(session, user_id, date_range)
        result = find_anomalies(rows, std_threshold, window_days, date_range.date_from, date_range.date_to)
        return AnomaliesResponse.model_validate(result, from_attributes=True)


analytics_service = AnalyticsService()
