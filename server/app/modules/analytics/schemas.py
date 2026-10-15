"""Analytics request and response schemas. Money is a decimal string; percents are 0–100."""

import datetime as dt
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class DateRange(BaseModel):
    """Inclusive, optional bounds; omitted means all time."""

    date_from: Optional[dt.date] = None
    date_to: Optional[dt.date] = None


# Dashboard


class CategorySliceResponse(_Out):
    """One category slice entry or result."""

    category: Optional[str] = Field(..., description="The category slug; null is every category past the top five")
    amount: Decimal = Field(..., description="Spend in the reference month")
    share_pct: float = Field(..., description="Share of the month's spend, 0–100")


class TrendPointResponse(_Out):
    """One trend point entry or result."""

    month: str = Field(..., description="YYYY-MM")
    income: Decimal
    expenses: Decimal


class DashboardResponse(_Out):
    """The home page's figures for the latest month with an active transaction."""

    reference_month: Optional[str] = Field(..., description="YYYY-MM; null for a user with no transactions")
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
    """One month flow entry or result."""

    month: str
    income: Decimal
    expenses: Decimal
    net: Decimal
    expense_change_pct: Optional[float] = Field(..., description="Against the month before; null after a zero month")


class SpendingResponse(_Out):
    """One spending entry or result."""

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
    """One category spend entry or result."""

    category: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float


class CategoryTrendResponse(_Out):
    """One category trend entry or result."""

    category: str
    first_month_total: Decimal
    last_month_total: Decimal
    growth_pct: float
    cv: Optional[float] = Field(..., description="Coefficient of variation of the monthly totals")


class CategoryBreakdownResponse(_Out):
    """One category breakdown entry or result."""

    total_expenses: Decimal
    top_categories: List[CategorySpendResponse]
    by_frequency: List[CategorySpendResponse]
    top_growing: List[CategoryTrendResponse]
    top_declining: List[CategoryTrendResponse]


# Merchants


class MerchantSpendResponse(_Out):
    """One merchant spend entry or result."""

    merchant: str
    total: Decimal
    count: int
    average: Decimal
    first_date: dt.date
    last_date: dt.date
    share_pct: float


class MerchantConcentrationResponse(_Out):
    """One merchant concentration entry or result."""

    top_5_share_pct: float
    top_10_share_pct: float
    herfindahl_index: float = Field(..., description="Σ(share %)² over every merchant, 0–10000")
    risk: Literal["low", "medium", "high"]
    unique_merchants: int


class MerchantBreakdownResponse(_Out):
    """One merchant breakdown entry or result."""

    total_expenses: Decimal
    top_by_spend: List[MerchantSpendResponse]
    top_by_frequency: List[MerchantSpendResponse]
    concentration: MerchantConcentrationResponse


# Recurring


class RecurringMerchantResponse(_Out):
    """One recurring merchant entry or result."""

    merchant: str
    charges: int
    months_charged: int
    median_charge: Decimal
    monthly_cost: Decimal = Field(..., description="Median charge × charges per month charged")


class HiddenSubscriptionResponse(_Out):
    """One hidden subscription entry or result."""

    merchant: str
    charges: int
    months_active: int
    average_charge: Decimal
    charges_per_month: float


class RecurringResponse(_Out):
    """One recurring entry or result."""

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
    """One weekday spend entry or result."""

    weekday: int = Field(..., description="0 is Monday")
    name: str
    total: Decimal
    count: int
    average: Decimal
    share_pct: float


class WeekPartResponse(_Out):
    """One week part entry or result."""

    days: int = Field(..., description="Calendar days of this kind in the range")
    total: Decimal
    per_day: Decimal


class MonthOfYearResponse(_Out):
    """One month of year entry or result."""

    month: int = Field(..., description="1 is January")
    average_spend: Decimal
    index: Optional[float] = Field(..., description="100 is the average month; null when the month is not in range")


class CategoryStabilityResponse(_Out):
    """One category stability entry or result."""

    category: str
    count: int
    cv: float
    stability: Literal["stable", "moderate", "volatile"]


class BehaviourResponse(_Out):
    """One behaviour entry or result."""

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
    """One outlier entry or result."""

    date: dt.date
    merchant: str
    category: str
    amount: Decimal = Field(..., description="The expense, positive")
    z_score: float
    window_mean: Decimal


class CategorySpikeResponse(_Out):
    """One category spike entry or result."""

    category: str
    recent_total: Decimal
    baseline_30d: Decimal
    spike_pct: float


class AnomaliesResponse(_Out):
    """One anomalies entry or result."""

    std_threshold: float
    window_days: int
    outliers: List[OutlierResponse]
    spikes: List[CategorySpikeResponse]
    spike_window_start: Optional[dt.date]
    spike_window_end: Optional[dt.date]
