"""Analytics routes under /analytics. Every one reads; none writes."""

from fastapi import APIRouter, Query, Request

from app.core.config import settings
from app.core.limiter import limiter
from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.analytics.dependencies import AnalyticsRange
from app.modules.analytics.schemas import (
    AnomaliesResponse,
    BehaviourResponse,
    CategoryBreakdownResponse,
    DashboardResponse,
    MerchantBreakdownResponse,
    RecurringResponse,
    SpendingResponse,
)
from app.modules.analytics.service import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])

LIMIT = settings.rate_limits.endpoints.TRANSACTIONS[0]


@router.get(
    "/dashboard",
    operation_id="getDashboard",
    response_model=DashboardResponse,
    summary="The home dashboard",
    description="Figures for the latest month holding an active transaction, and the six months up to it.",
)
@limiter.limit(LIMIT)
async def get_dashboard(request: Request, db_session: DbSession, user: CurrentUser) -> DashboardResponse:
    """The home dashboard figures."""
    return await analytics_service.dashboard(db_session, user.id)


@router.get(
    "/spending",
    operation_id="getSpending",
    response_model=SpendingResponse,
    summary="Income, expenses and net",
    description="Totals, averages and a zero-filled per-month series. Bounds are inclusive and optional.",
)
@limiter.limit(LIMIT)
async def get_spending(
    request: Request, db_session: DbSession, user: CurrentUser, date_range: AnalyticsRange
) -> SpendingResponse:
    """Income, expenses and net over the range."""
    return await analytics_service.spending(db_session, user.id, date_range)


@router.get(
    "/categories",
    operation_id="getCategoryBreakdown",
    response_model=CategoryBreakdownResponse,
    summary="Spend by category",
    description="Categories ranked by spend and by count, and the fastest growing and declining.",
)
@limiter.limit(LIMIT)
async def get_categories(
    request: Request,
    db_session: DbSession,
    user: CurrentUser,
    date_range: AnalyticsRange,
    top_n: int = Query(10, ge=1, le=50, description="How many categories each ranking keeps"),
) -> CategoryBreakdownResponse:
    """Spend by category over the range."""
    return await analytics_service.categories(db_session, user.id, date_range, top_n)


@router.get(
    "/merchants",
    operation_id="getMerchantBreakdown",
    response_model=MerchantBreakdownResponse,
    summary="Spend by merchant",
    description="Merchants ranked by spend and by count, and how concentrated spending is.",
)
@limiter.limit(LIMIT)
async def get_merchants(
    request: Request,
    db_session: DbSession,
    user: CurrentUser,
    date_range: AnalyticsRange,
    top_n: int = Query(15, ge=1, le=50, description="How many merchants each ranking keeps"),
) -> MerchantBreakdownResponse:
    """Spend by merchant over the range."""
    return await analytics_service.merchants(db_session, user.id, date_range, top_n)


@router.get(
    "/recurring",
    operation_id="getRecurring",
    response_model=RecurringResponse,
    summary="Recurring spend",
    description="Spend flagged recurring, its monthly cost per merchant, and unflagged small regular charges.",
)
@limiter.limit(LIMIT)
async def get_recurring(
    request: Request, db_session: DbSession, user: CurrentUser, date_range: AnalyticsRange
) -> RecurringResponse:
    """Recurring spend over the range."""
    return await analytics_service.recurring(db_session, user.id, date_range)


@router.get(
    "/behaviour",
    operation_id="getBehaviour",
    response_model=BehaviourResponse,
    summary="Spending patterns",
    description="By weekday, weekday against weekend, by calendar month, and how steady each category is.",
)
@limiter.limit(LIMIT)
async def get_behaviour(
    request: Request, db_session: DbSession, user: CurrentUser, date_range: AnalyticsRange
) -> BehaviourResponse:
    """Spending patterns over the range."""
    return await analytics_service.behaviour(db_session, user.id, date_range)


@router.get(
    "/anomalies",
    operation_id="getAnomalies",
    response_model=AnomaliesResponse,
    summary="Unusual spending",
    description="Expenses far above their trailing window, and categories spending more than usual lately.",
)
@limiter.limit(LIMIT)
async def get_anomalies(
    request: Request,
    db_session: DbSession,
    user: CurrentUser,
    date_range: AnalyticsRange,
    std_threshold: float = Query(2.5, ge=1.0, le=5.0, description="Standard deviations above the window mean"),
    window_days: int = Query(30, ge=7, le=90, description="Days before an expense that it is compared with"),
) -> AnomaliesResponse:
    """Outliers and category spikes over the range."""
    return await analytics_service.anomalies(db_session, user.id, date_range, std_threshold, window_days)
