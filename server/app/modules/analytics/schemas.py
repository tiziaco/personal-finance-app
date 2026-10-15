"""Analytics request and response schemas. Money is a decimal string; percents are 0–100."""

import datetime as dt
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.modules.analytics.domain.behaviour import Stability
from app.modules.analytics.domain.merchants import Risk


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# The dates analytics covers. An explicit bound outside them is a 422; a row outside them is left out.
MIN_DATE = dt.date(1900, 1, 1)
MAX_DATE = dt.date(2100, 12, 31)


class DateRange(BaseModel):
    """Inclusive, optional bounds; omitted means all time, MIN_DATE to MAX_DATE."""

    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None


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


class DashboardResponse(_Out):
    """The home page's figures for the reference month: the latest month with a transaction, up to this month."""

    reference_month: Optional[str] = Field(
        ..., description="YYYY-MM: latest month with a transaction up to this month; null with no transactions"
    )
    total_spent: Decimal
    recurring_spent: Decimal = Field(..., description="Expenses flagged recurring in the reference month")
    recurring_count: int
    net_balance: Decimal = Field(..., description="Income minus expenses in the reference month")
    average_cashflow: Decimal = Field(..., description="Mean monthly net over cashflow_months")
    cashflow_months: int = Field(..., description="1–3 months ending at the reference month; 0 with no data")
    spending_by_category: List[CategorySliceResponse]
    monthly_trend: List[TrendPointResponse] = Field(..., description="The six months ending at the reference month")


# Spending


class MonthFlowResponse(_Out):
    """One month's income, expenses and net, with the change in expenses against the month before."""

    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    expense_change_pct: Optional[float] = Field(..., description="Against the month before; null after a zero month")


class SpendingResponse(_Out):
    """Income, expenses and net over the range, with monthly averages, burn rate and a monthly series."""

    date_from: Optional[dt.date] = Field(..., description="The first day covered")
    date_to: Optional[dt.date] = Field(..., description="The last day covered")
    total_income: Decimal
    total_expenses: Decimal
    net: Decimal
    transaction_count: int
    average_income: Decimal
    average_expense: Decimal
    average_monthly_income: Decimal
    average_monthly_expenses: Decimal
    burn_rate: Decimal = Field(..., description="Average monthly expenses minus average monthly income")
    months: List[MonthFlowResponse]


# Categories


class CategorySpendResponse(_Out):
    """One category's spend in the range: total, count, average and share of all expenses."""

    category: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float


class CategoryTrendResponse(_Out):
    """How one category's monthly spend moved between the first and last month of the range, and how steady it was."""

    category: str
    first_month_total: Decimal
    last_month_total: Decimal
    growth_pct: float
    cv: Optional[float] = Field(..., description="Coefficient of variation of the monthly totals")


class CategoryBreakdownResponse(_Out):
    """Spend by category over the range: the biggest, most frequent, fastest growing and declining."""

    total_expenses: Decimal
    top_categories: List[CategorySpendResponse]
    by_frequency: List[CategorySpendResponse]
    top_growing: List[CategoryTrendResponse]
    top_declining: List[CategoryTrendResponse]


# Merchants


class MerchantSpendResponse(_Out):
    """One merchant's spend in the range: total, count, average, first and last date, and share."""

    merchant: str
    total: Decimal
    count: int
    average: Decimal
    first_date: dt.date
    last_date: dt.date
    share_pct: float


class MerchantConcentrationResponse(_Out):
    """How concentrated spending is across merchants: top-5 and top-10 shares, the Herfindahl index and a risk band."""

    top_5_share_pct: float
    top_10_share_pct: float
    herfindahl_index: float = Field(..., description="Σ(share %)² over every merchant, 0–10000")
    risk: Risk
    unique_merchants: int


class MerchantBreakdownResponse(_Out):
    """Spend by merchant over the range: the top by spend and by frequency, and the concentration."""

    total_expenses: Decimal
    top_by_spend: List[MerchantSpendResponse]
    top_by_frequency: List[MerchantSpendResponse]
    concentration: MerchantConcentrationResponse


# Recurring


class RecurringMerchantResponse(_Out):
    """One merchant charged on a recurring basis: its charges, months charged, median charge and monthly cost."""

    merchant: str
    charges: int
    months_charged: int
    median_charge: Decimal
    monthly_cost: Decimal = Field(..., description="Median charge × charges per month charged")


class HiddenSubscriptionResponse(_Out):
    """An unflagged merchant charged small amounts often: 3 or more charges a month, averaging 50 or less."""

    merchant: str
    charges: int
    months_active: int
    average_charge: Decimal
    charges_per_month: float


class RecurringResponse(_Out):
    """Recurring spend over the range: totals, monthly cost, each recurring merchant and hidden subscriptions."""

    total_expenses: Decimal
    recurring_total: Decimal
    recurring_count: int
    amount_share_pct: float
    count_share_pct: float
    monthly_recurring_cost: Decimal
    merchants: List[RecurringMerchantResponse]
    hidden_subscriptions: List[HiddenSubscriptionResponse]


# Behaviour


class WeekdaySpendResponse(_Out):
    """One weekday's spend in the range: total, count, average and share of all expenses."""

    weekday: int = Field(..., description="0 is Monday")
    name: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float


class WeekPartResponse(_Out):
    """Spend on weekdays or on weekends in the range: calendar days, total and spend per day."""

    days: int = Field(..., description="Calendar days of this kind in the range")
    total: Decimal
    per_day: Decimal


class MonthOfYearResponse(_Out):
    """Average spend for one calendar month of the year, with an index against the average month."""

    month: int = Field(..., description="1 is January")
    average_spend: Decimal
    index: Optional[float] = Field(..., description="100 is the average month; null when the month is not in range")


class CategoryStabilityResponse(_Out):
    """How steady one category's expense amounts are, from their coefficient of variation."""

    category: str
    count: int
    cv: float
    stability: Stability


class BehaviourResponse(_Out):
    """Spending patterns over the range: by weekday, weekday against weekend, seasonality and category stability."""

    by_weekday: List[WeekdaySpendResponse]
    weekday: WeekPartResponse
    weekend: WeekPartResponse
    weekend_bias_pct: Optional[float]
    seasonality: List[MonthOfYearResponse]
    stability: List[CategoryStabilityResponse]
    stable_share_pct: float
    moderate_share_pct: float
    volatile_share_pct: float
    expense_change_pct: Optional[float] = Field(..., description="Between the range's last two months")


# Anomalies


class OutlierResponse(_Out):
    """One expense far above the expenses of its trailing window, with its z-score and the window's mean."""

    date: dt.date
    merchant: str
    category: str
    amount: Decimal = Field(..., description="The expense, positive")
    z_score: float
    window_mean: Decimal


class CategorySpikeResponse(_Out):
    """One category whose last 30 days spend well above its average 30 days over the rest of the range."""

    category: str
    recent_total: Decimal
    baseline_30d: Decimal
    spike_pct: float


class AnomaliesResponse(_Out):
    """Outlier expenses and category spikes over the range, with the thresholds used."""

    std_threshold: float
    window_days: int
    outliers: List[OutlierResponse]
    spikes: List[CategorySpikeResponse]
    spike_window_start: Optional[dt.date]
    spike_window_end: Optional[dt.date]
