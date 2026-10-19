"""One user's usable rows and today, loaded once; every analysis over any window runs in memory."""

import datetime as dt
from dataclasses import dataclass
from typing import Optional

from app.modules.analytics.domain.anomalies import find_anomalies
from app.modules.analytics.domain.behaviour import behaviour_analysis
from app.modules.analytics.domain.categories import category_breakdown
from app.modules.analytics.domain.dashboard import build_dashboard
from app.modules.analytics.domain.merchants import merchant_breakdown
from app.modules.analytics.domain.period import Period, resolve_period
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
from app.modules.transaction import AnalysisRow


@dataclass(frozen=True)
class AnalyticsHistory:
    """One user's usable rows and today, loaded once; every analysis over any window, in memory.

    Every row is held, not only a period's: months=N, the month before the period and the rolling
    average need rows outside it (the period rules in `docs/product/features/analytics.md`).
    """

    rows: tuple[AnalysisRow, ...]
    today: dt.date

    def period(self, date_range: DateRange) -> Optional[Period]:
        """The period the range resolves to over these rows; None when there is nothing to resolve."""
        return resolve_period(
            self.rows,
            self.today,
            date_from=date_range.date_from,
            date_to=date_range.date_to,
            months=date_range.months,
        )

    def dashboard(self) -> DashboardResponse:
        """The home dashboard figures."""
        return DashboardResponse.model_validate(build_dashboard(self.rows, today=self.today), from_attributes=True)

    def spending(self, date_range: DateRange) -> SpendingResponse:
        """Income, expenses and net over the period, and the current month so far."""
        return SpendingResponse.model_validate(spending_summary(self.rows, self.period(date_range), today=self.today))

    def categories(self, date_range: DateRange, top_n: int) -> CategoryBreakdownResponse:
        """Spend by category over the range."""
        return CategoryBreakdownResponse.model_validate(
            category_breakdown(self.rows, self.period(date_range), top_n, today=self.today)
        )

    def merchants(self, date_range: DateRange, top_n: int) -> MerchantBreakdownResponse:
        """Spend by merchant over the period."""
        return MerchantBreakdownResponse.model_validate(merchant_breakdown(self.rows, self.period(date_range), top_n))

    def recurring(self, date_range: DateRange) -> RecurringResponse:
        """Recurring spend over the period."""
        return RecurringResponse.model_validate(recurring_analysis(self.rows, self.period(date_range)))

    def behaviour(self, date_range: DateRange) -> BehaviourResponse:
        """Spending patterns over the range."""
        return BehaviourResponse.model_validate(behaviour_analysis(self.rows, self.period(date_range)))

    def anomalies(self, date_range: DateRange, std_threshold: float, window_days: int) -> AnomaliesResponse:
        """Outliers and category spikes over the period."""
        return AnomaliesResponse.model_validate(
            find_anomalies(self.rows, self.period(date_range), std_threshold, window_days)
        )
