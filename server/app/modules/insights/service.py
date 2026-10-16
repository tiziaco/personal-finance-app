"""Insights service."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.insights.repository import insight_repository


class InsightsService:
    """Orchestrates the insights module; the agent and the routes arrive in later tasks."""

    @staticmethod
    async def delete_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Remove everything the module stores for the user."""
        await insight_repository.delete_for_user(session, user_id)


insights_service = InsightsService()
