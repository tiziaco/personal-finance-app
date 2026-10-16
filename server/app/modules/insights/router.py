"""Insights routes under /insights."""

from fastapi import APIRouter, Request

from app.core.config import settings
from app.core.limiter import limiter, user_or_ip_key
from app.database.dependencies import DbSession
from app.modules.account import CurrentUser
from app.modules.insights.schemas import InsightsResponse
from app.modules.insights.service import insights_service

router = APIRouter(prefix="/insights", tags=["insights"])

LIMIT = settings.rate_limits.endpoints.INSIGHTS[0]


@router.get(
    "",
    operation_id="getInsights",
    response_model=InsightsResponse,
    summary="The stored insights",
    description="The user's latest insights and their status: no_data, none, stale or fresh. Never calls the model.",
)
@limiter.limit(LIMIT, key_func=user_or_ip_key)
async def get_insights(request: Request, db_session: DbSession, user: CurrentUser) -> InsightsResponse:
    """The stored insights and their freshness."""
    return await insights_service.read(db_session, user.id)


@router.post(
    "/generate",
    operation_id="generateInsights",
    response_model=InsightsResponse,
    summary="Generate insights",
    description="Writes a new set from the user's figures, replacing the stored one. 503 INSIGHTS_UNAVAILABLE when the model fails, leaving the stored set untouched.",
)
@limiter.limit(LIMIT, key_func=user_or_ip_key)
async def generate_insights(request: Request, db_session: DbSession, user: CurrentUser) -> InsightsResponse:
    """Generate and store a new set of insights."""
    return await insights_service.generate(db_session, user.id)
