"""Analytics read-only endpoints — feeds dashboard and per-tab analytics page."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.database import DbSession
from app.core.limiter import limiter
from app.schemas.analytics import AnalyticsFilters, AnalyticsResponse, DashboardResponse
from app.services.analytics.service import analytics_service

router = APIRouter()


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Dashboard summary",
    description=(
        "Composed snapshot across spending, categories, recurring, and trends. "
        "Designed for the main dashboard — fast, opinionated, no extra params."
    ),
)
@limiter.limit("30/minute")
async def get_dashboard(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
) -> DashboardResponse:
    data = await analytics_service.get_dashboard(
        db, user.id, filters.date_from, filters.date_to
    )
    return DashboardResponse(**data, generated_at=datetime.now(timezone.utc))


@router.get(
    "/spending",
    response_model=AnalyticsResponse,
    summary="Spending overview",
    description="Spending overview, income vs expenses, monthly trend, and burn rate.",
)
@limiter.limit("30/minute")
async def get_spending(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
) -> AnalyticsResponse:
    data = await analytics_service.get_spending(
        db, user.id, filters.date_from, filters.date_to
    )
    return AnalyticsResponse(data=data, generated_at=datetime.now(timezone.utc))


@router.get(
    "/categories",
    response_model=AnalyticsResponse,
    summary="Category breakdown",
    description="Top categories by spend, frequency vs impact, and category trends.",
)
@limiter.limit("30/minute")
async def get_categories(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
    top_n: int = Query(10, ge=1, le=50, description="Number of top categories to return"),
) -> AnalyticsResponse:
    data = await analytics_service.get_categories(
        db, user.id, filters.date_from, filters.date_to, top_n=top_n
    )
    return AnalyticsResponse(data=data, generated_at=datetime.now(timezone.utc))


@router.get(
    "/merchants",
    response_model=AnalyticsResponse,
    summary="Merchant insights",
    description="Top merchants by spend and frequency, plus concentration risk metrics.",
)
@limiter.limit("30/minute")
async def get_merchants(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
    top_n: int = Query(15, ge=1, le=50, description="Number of top merchants to return"),
) -> AnalyticsResponse:
    data = await analytics_service.get_merchants(
        db, user.id, filters.date_from, filters.date_to, top_n=top_n
    )
    return AnalyticsResponse(data=data, generated_at=datetime.now(timezone.utc))


@router.get(
    "/recurring",
    response_model=AnalyticsResponse,
    summary="Recurring & subscriptions",
    description=(
        "Recurring expenses, hidden subscriptions, monthly recurring cost, "
        "and spending stability/predictability profile."
    ),
)
@limiter.limit("30/minute")
async def get_recurring(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
) -> AnalyticsResponse:
    data = await analytics_service.get_recurring(
        db, user.id, filters.date_from, filters.date_to
    )
    return AnalyticsResponse(data=data, generated_at=datetime.now(timezone.utc))


@router.get(
    "/behavior",
    response_model=AnalyticsResponse,
    summary="Behavioral patterns",
    description=(
        "Day-of-week spending patterns, seasonal sensitivity, "
        "and volatility classification (stable vs volatile categories)."
    ),
)
@limiter.limit("30/minute")
async def get_behavior(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
) -> AnalyticsResponse:
    data = await analytics_service.get_behavior(
        db, user.id, filters.date_from, filters.date_to
    )
    return AnalyticsResponse(data=data, generated_at=datetime.now(timezone.utc))


@router.get(
    "/anomalies",
    response_model=AnalyticsResponse,
    summary="Anomaly detection",
    description=(
        "Outlier transactions detected via rolling z-score, "
        "recent category spikes, and volatile spending categories."
    ),
)
@limiter.limit("30/minute")
async def get_anomalies(
    request: Request,
    db: DbSession,
    user: CurrentUser,
    filters: AnalyticsFilters = Depends(),
    std_threshold: float = Query(2.5, description="Z-score threshold for anomaly detection"),
    rolling_window: int = Query(
        30, ge=7, le=90, description="Rolling window in days for baseline calculation"
    ),
) -> AnalyticsResponse:
    data = await analytics_service.get_anomalies(
        db,
        user.id,
        filters.date_from,
        filters.date_to,
        std_threshold=std_threshold,
        rolling_window=rolling_window,
    )
    return AnalyticsResponse(data=data, generated_at=datetime.now(timezone.utc))
