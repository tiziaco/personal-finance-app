"""Insights endpoint — serves cached AI-generated financial insights."""

from fastapi import APIRouter, Request

from app.api.dependencies.auth import CurrentUser
from app.api.dependencies.database import DbSession
from app.core.limiter import limiter
from app.schemas.insights import Insight, InsightsResponse
from app.services.insights.service import insights_service

router = APIRouter()


@router.get(
    "",
    response_model=InsightsResponse,
    summary="Financial insights",
    description=(
        "AI-generated financial insights cached per user. "
        "On first call (no cache), generates synchronously. "
        "Regenerates automatically after bulk transaction import."
    ),
)
@limiter.limit("10/minute")
async def get_insights(
    request: Request,
    db: DbSession,
    user: CurrentUser,
) -> InsightsResponse:
    row = await insights_service.get_insights(db, user.id)
    return InsightsResponse(
        insights=[Insight(**i) for i in row.insights],
        generated_at=row.generated_at,
    )
