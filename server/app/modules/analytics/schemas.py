"""Analytics request and response schemas. Money is a decimal string; percents are 0–100."""

import datetime as dt
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.analytics.domain.behaviour import Stability
from app.modules.analytics.exceptions import InvalidDateRangeError
from app.modules.transaction import MAX_DATE, MIN_DATE


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DateRange(BaseModel):
    """Inclusive, optional bounds (omitted means all time), or the last `months` finished months, not both."""

    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None
    months: Optional[int] = None

    @model_validator(mode="after")
    def _check(self) -> "DateRange":
        context = {"date_from": str(self.date_from), "date_to": str(self.date_to), "months": self.months}
        for name in ("date_from", "date_to"):
            value = getattr(self, name)
            if value is not None and not MIN_DATE <= value <= MAX_DATE:
                raise InvalidDateRangeError(f"{name} must be between {MIN_DATE} and {MAX_DATE}", **context)
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise InvalidDateRangeError("date_from is after date_to", **context)
        if self.months is not None:
            if not 1 <= self.months <= 120:
                raise InvalidDateRangeError("months must be between 1 and 120", **context)
            if self.date_from or self.date_to:
                raise InvalidDateRangeError("months cannot be combined with date_from or date_to", **context)
        return self


# Dashboard


class CategorySliceResponse(_Out):
    """One slice of the dashboard's spending chart: a category (or the rest) with its spend and share."""

    category: Optional[str] = Field(..., description="The category slug; null is every category past the top five")
    amount: Decimal = Field(..., description="Spend in the reference month")
    share_pct: float = Field(..., description="Share of the month's spend, 0–100")


class TrendPointResponse(_Out):
    """One month of the dashboard's trend chart: income and expenses."""

    month: str = Field(..., description="YYYY-MM")
    income: Decimal
    expenses: Decimal


class MonthToDateResponse(_Out):
    """The current month from day 1 to its last transaction, against the same days of the month before."""

    month: str = Field(..., description="YYYY-MM, the current month")
    through: dt.date = Field(..., description="The day of the current month's last transaction")
    income: Decimal
    expenses: Decimal
    previous_month: str = Field(..., description="YYYY-MM")
    previous_income: Decimal = Field(..., description="Income in the previous month's days 1 to through's day")
    previous_expenses: Decimal = Field(..., description="Expenses in the previous month's days 1 to through's day")
    income_change_pct: Optional[float] = Field(..., description="Against previous_income; null when it is 0")
    expenses_change_pct: Optional[float] = Field(..., description="Against previous_expenses; null when it is 0")


class DashboardResponse(_Out):
    """The home page's figures for the reference month: the latest finished month with a transaction."""

    reference_month: Optional[str] = Field(
        ...,
        description="YYYY-MM: latest finished month with a transaction, else the current month; null with no data",
    )
    reference_partial: bool = Field(..., description="True when the reference month is the month in progress")
    total_spent: Decimal
    recurring_spent: Decimal = Field(..., description="Expenses flagged recurring in the reference month")
    recurring_count: int
    net_balance: Decimal = Field(..., description="Income minus expenses in the reference month")
    average_cashflow: Decimal = Field(..., description="Mean monthly net over cashflow_months")
    cashflow_months: int = Field(..., description="1–3 months ending at the reference month; 0 with no data")
    spending_by_category: List[CategorySliceResponse]
    monthly_trend: List[TrendPointResponse] = Field(
        ..., description="Up to six months ending at the reference month, not before the data's first month"
    )
    month_to_date: Optional[MonthToDateResponse] = Field(
        ..., description="The current month so far against the month before; null when it holds no transaction"
    )


# Spending


class MonthFlowResponse(_Out):
    """One month's income, expenses and net, with the change in expenses, a rolling average and the savings rate."""

    month: str = Field(..., description="YYYY-MM")
    income: Decimal
    expenses: Decimal
    net: Decimal
    expense_change_pct: Optional[float] = Field(
        ...,
        description="Against the month before, which may precede the period; null when either month is partial, "
        "the month before is outside the data or spent nothing",
    )
    partial: bool = Field(..., description="The period covers only some of the month's days")
    expenses_rolling_avg_3m: Optional[Decimal] = Field(
        ...,
        description="Mean expenses of this month and the two before it, which may precede the period; null when "
        "any of the three is partial or before the data's first month",
    )
    savings_rate_pct: Optional[float] = Field(..., description="Net ÷ income × 100; null when income is 0")


class LatestMonthResponse(_Out):
    """The period's last whole month against the period's monthly averages, which include it."""

    month: str = Field(..., description="YYYY-MM")
    income: Decimal
    expenses: Decimal
    income_vs_average_pct: Optional[float] = Field(
        ..., description="Against average_monthly_income; null when that average is 0"
    )
    expenses_vs_average_pct: Optional[float] = Field(
        ..., description="Against average_monthly_expenses; null when that average is 0"
    )


class SpendingResponse(_Out):
    """Income, expenses and net over the period, with weighted monthly averages, a monthly series and month-to-date."""

    date_from: Optional[dt.date] = Field(..., description="First day of the resolved period; null when empty")
    date_to: Optional[dt.date] = Field(..., description="Last day of the resolved period; null when empty")
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal
    transaction_count: int
    average_income: Decimal = Field(..., description="Per transaction")
    average_expense: Decimal = Field(..., description="Per transaction")
    average_monthly_income: Decimal = Field(
        ..., description="Total income ÷ the period's months, a partial month counting for the share of it covered"
    )
    average_monthly_expenses: Decimal = Field(
        ..., description="Total expenses ÷ the period's months, a partial month counting for the share of it covered"
    )
    average_monthly_net: Decimal = Field(
        ..., description="Net ÷ the period's months, a partial month counting for the share of it covered"
    )
    burn_rate: Decimal = Field(
        ..., description="(Total expenses − total income) ÷ the period's months; negative while saving"
    )
    savings_rate_pct: Optional[float] = Field(..., description="Net ÷ income × 100; null when income is 0")
    months: List[MonthFlowResponse]
    latest_month: Optional[LatestMonthResponse] = Field(
        ..., description="The period's last whole month; null when it has none"
    )
    month_to_date: Optional[MonthToDateResponse] = Field(
        ...,
        description="The current month so far, independent of the period; null when it holds no transaction",
    )


# Categories


class CategorySpendResponse(_Out):
    """One category's spend in the period: total, count, average, share of all expenses, and against the previous period."""

    category: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float
    previous_total: Optional[Decimal] = Field(
        ..., description="The category's spend in the previous period; null when there is no previous period"
    )
    change_pct: Optional[float] = Field(
        ..., description="Change from previous_total to total, in percent; null when previous_total is 0 or null"
    )


class CategoryTrendResponse(_Out):
    """A category's monthly average over the earlier and the later half of the period's whole months."""

    category: str
    earlier_monthly_average: Decimal
    later_monthly_average: Decimal
    change_amount: Decimal = Field(..., description="later_monthly_average minus earlier_monthly_average")
    change_pct: Optional[float] = Field(
        ..., description="Change over the earlier average, in percent; -100 when the later half is zero; null when new"
    )


class CategoryBreakdownResponse(_Out):
    """Spend by category over the period: the biggest, most frequent, growing and declining."""

    date_from: Optional[dt.date] = Field(..., description="First day of the resolved period; null when empty")
    date_to: Optional[dt.date] = Field(..., description="Last day of the resolved period; null when empty")
    previous_date_from: Optional[dt.date] = Field(
        ..., description="The first day of the previous period of the same length; null when it holds no transaction"
    )
    previous_date_to: Optional[dt.date] = Field(..., description="The last day of the previous period; null as above")
    total_expenses: Decimal
    top_categories: List[CategorySpendResponse]
    by_frequency: List[CategorySpendResponse]
    top_growing: List[CategoryTrendResponse]
    top_declining: List[CategoryTrendResponse]


# Merchants


class MerchantSpendResponse(_Out):
    """One merchant's spend in the period: total, count, average, first and last date, and share."""

    merchant: str
    total: Decimal
    count: int
    average: Decimal
    first_date: dt.date
    last_date: dt.date
    share_pct: float


class MerchantConcentrationResponse(_Out):
    """How concentrated spending is across merchants: top-5 and top-10 shares, and the Herfindahl index."""

    top_5_share_pct: float
    top_10_share_pct: float
    herfindahl_index: float = Field(..., description="Σ(share %)² over every merchant, 0–10000")
    unique_merchants: int


class MerchantBreakdownResponse(_Out):
    """Spend by merchant over the period: the top by spend and by frequency, and the concentration."""

    date_from: Optional[dt.date] = Field(..., description="First day of the resolved period; null when empty")
    date_to: Optional[dt.date] = Field(..., description="Last day of the resolved period; null when empty")
    total_expenses: Decimal
    top_by_spend: List[MerchantSpendResponse]
    top_by_frequency: List[MerchantSpendResponse]
    concentration: MerchantConcentrationResponse


# Recurring


class RecurringMerchantResponse(_Out):
    """One merchant flagged recurring: its charges, billing rhythm, monthly cost, and whether it still charges."""

    merchant: str
    charges: int
    months_charged: int
    median_charge: Decimal
    interval_days: Optional[int] = Field(
        ..., description="Median gap in days between consecutive charges; null with one charge"
    )
    monthly_cost: Decimal = Field(
        ...,
        description=(
            "Median charge ÷ the whole months between charges when they are 25 days or more apart, "
            "else × 30.436875 ÷ interval_days; with one charge, ÷ the period's months"
        ),
    )
    last_charge: dt.date
    active: bool = Field(..., description="False when the period ends more than 1.5 × interval_days after last_charge")


class HiddenSubscriptionResponse(_Out):
    """An unflagged merchant charging like a subscription: in 3+ months, 25–35 days apart, steady, at most 50."""

    merchant: str
    charges: int
    months_active: int
    average_charge: Decimal
    charges_per_month: float


class RecurringResponse(_Out):
    """Recurring spend over the period: totals, monthly cost, each recurring merchant and hidden subscriptions."""

    date_from: Optional[dt.date] = Field(..., description="First day of the resolved period; null when empty")
    date_to: Optional[dt.date] = Field(..., description="Last day of the resolved period; null when empty")
    total_expenses: Decimal
    recurring_total: Decimal
    recurring_count: int
    amount_share_pct: float
    count_share_pct: float
    monthly_recurring_cost: Decimal = Field(..., description="The sum of active merchants' monthly cost")
    merchants: List[RecurringMerchantResponse]
    hidden_subscriptions: List[HiddenSubscriptionResponse]


# Behaviour


class WeekdaySpendResponse(_Out):
    """One weekday's spend in the period: total, count, average and share of all expenses."""

    weekday: int = Field(..., description="0 is Monday")
    name: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float
    days: int = Field(..., description="How many times this weekday occurs in the period")
    per_day: Decimal = Field(..., description="Total spend ÷ days")


class WeekPartResponse(_Out):
    """Spend on weekdays or on weekends in the period: calendar days, total and spend per day."""

    days: int = Field(..., description="Calendar days of this kind in the period")
    total: Decimal
    per_day: Decimal


class MonthOfYearResponse(_Out):
    """Average spend for one calendar month of the year, with an index against the average month."""

    month: int = Field(..., description="1 is January")
    average_spend: Decimal
    index: Optional[float] = Field(
        ..., description="100 is the average whole month; null when years is 0 or the average month is 0"
    )
    years: int = Field(..., description="Whole months of this calendar month in the period")


class CategoryStabilityResponse(_Out):
    """How steady one category's expense amounts are, from their coefficient of variation."""

    category: str
    count: int = Field(..., description="Expenses in the months judged")
    months: int = Field(..., description="Whole months judged, from the first with spend")
    cv: float
    stability: Stability


class BehaviourResponse(_Out):
    """Spending patterns over the period: by weekday, weekday against weekend, seasonality and category stability."""

    date_from: Optional[dt.date] = Field(..., description="First day of the resolved period; null when empty")
    date_to: Optional[dt.date] = Field(..., description="Last day of the resolved period; null when empty")
    by_weekday: List[WeekdaySpendResponse]
    weekday: WeekPartResponse
    weekend: WeekPartResponse
    weekend_bias_pct: Optional[float]
    seasonality: List[MonthOfYearResponse]
    stability: List[CategoryStabilityResponse]
    stable_share_pct: float
    moderate_share_pct: float
    volatile_share_pct: float
    expense_change_pct: Optional[float] = Field(..., description="Between the period's last two whole months")


# Anomalies


class OutlierResponse(_Out):
    """One expense in the period far above the earlier expenses of its category in its trailing window.

    Recurring-flagged expenses are never outliers and never in a window; a window may reach before the period.
    """

    date: dt.date
    merchant: str
    category: str
    amount: Decimal = Field(..., description="The expense, positive")
    z_score: float
    window_mean: Decimal = Field(..., description="The mean of the category's expenses in the window")


class CategorySpikeResponse(_Out):
    """One category whose spend in the period's last 30 days is well above its average 30 days before them."""

    category: str
    recent_total: Decimal = Field(..., description="Spend in the spike window")
    baseline_30d: Decimal = Field(..., description="Average 30 days' spend from the period's first day to the window")
    increase_amount: Decimal = Field(..., description="recent_total − baseline_30d; spikes are ranked by it")
    spike_pct: float


class AnomaliesResponse(_Out):
    """Outlier expenses and category spikes over the period, with the thresholds used."""

    date_from: Optional[dt.date] = Field(..., description="First day of the resolved period; null when empty")
    date_to: Optional[dt.date] = Field(..., description="Last day of the resolved period; null when empty")
    std_threshold: float
    window_days: int
    outliers: List[OutlierResponse] = Field(..., description="The top 20 by z-score")
    spikes: List[CategorySpikeResponse]
    spike_window_start: Optional[dt.date] = Field(
        ..., description="First day of the period's last 30 days; null when spikes were not checked"
    )
    spike_window_end: Optional[dt.date] = Field(
        ..., description="Last day of the period; null when spikes were not checked"
    )
