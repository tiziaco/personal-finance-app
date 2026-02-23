"""Insights service — generate, store, and retrieve cached AI insights."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.agents.insights.agent import InsightsConfig, generate_insights
from app.core.logging import logger
from app.models.insight import Insight as InsightModel
from app.services.insights.exceptions import InsightsError
from app.services.llm import llm_service
from app.services.transaction.service import TransactionService


class InsightsService:
    """Stateless insights service.

    Orchestrates: DB fetch → Polars DataFrame → LangGraph insights graph → DB upsert.
    """

    @staticmethod
    async def load_and_generate(db: AsyncSession, user_id: str) -> None:
        """Generate insights and upsert the Insight row for the user.

        Called as a background task after bulk import, or synchronously on
        the first GET when no cached row exists.

        Steps:
        1. Load user transactions as a Polars DataFrame via TransactionService.
        2. Run generate_insights() (LangGraph graph) with LLM enrichment.
        3. Upsert the Insight row (update existing or insert new).

        Args:
            db: Active database session.
            user_id: Authenticated user's ID.

        Raises:
            InsightsError: If the LangGraph graph fails to execute.
        """
        df = await TransactionService.load_dataframe(db, user_id)

        config = InsightsConfig(
            enable_llm_enrichment=True,
            llm_model=llm_service.get_llm(),
        )

        try:
            result = await generate_insights(df, user_id=user_id, config=config)
        except Exception as e:
            raise InsightsError(f"Insights generation failed: {e}") from e

        formatted_insights = result.get("formatted_insights", [])
        serialized = [i.model_dump() for i in formatted_insights]

        # Upsert: update existing row or create a new one
        stmt = select(InsightModel).where(InsightModel.user_id == user_id)
        result_db = await db.execute(stmt)
        existing = result_db.scalar_one_or_none()

        now = datetime.now(UTC)

        if existing:
            existing.insights = serialized
            existing.generated_at = now
            db.add(existing)
        else:
            row = InsightModel(
                user_id=user_id,
                insights=serialized,
                generated_at=now,
            )
            db.add(row)

        await db.flush()

        logger.info(
            "insights_generated",
            user_id=user_id,
            count=len(serialized),
        )

    @staticmethod
    async def get_insights(db: AsyncSession, user_id: str) -> InsightModel:
        """Return the cached Insight row for the user.

        If no row exists yet (first-ever call), generates synchronously first.

        Args:
            db: Active database session.
            user_id: Authenticated user's ID.

        Returns:
            The InsightModel row with insights list and generated_at.

        Raises:
            InsightsError: If generation is triggered and fails.
        """
        stmt = select(InsightModel).where(InsightModel.user_id == user_id)
        result = await db.execute(stmt)
        row = result.scalar_one_or_none()

        if row is None:
            await InsightsService.load_and_generate(db, user_id)
            result = await db.execute(stmt)
            row = result.scalar_one_or_none()

        if row is None:
            raise InsightsError("Failed to generate insights for user", user_id=user_id)

        return row


insights_service = InsightsService()
