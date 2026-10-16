"""Insight repository: every query, each one scoped by user_id."""

import datetime as dt
import uuid
from typing import Any, Optional

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid_utils.compat import uuid7

from app.modules.insights.models import InsightSet


class InsightRepository:
    """Repository for the insight_set table."""

    @staticmethod
    async def get(session: AsyncSession, user_id: uuid.UUID) -> Optional[InsightSet]:
        """The user's insight set, or None."""
        statement = select(InsightSet).where(InsightSet.user_id == user_id)
        return (await session.execute(statement)).scalar_one_or_none()

    @staticmethod
    async def replace(
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        generated_at: dt.datetime,
        reference_month: str,
        month_to_date_through: Optional[dt.date],
        prompt_version: str,
        insights: list[dict[str, Any]],
    ) -> InsightSet:
        """Insert the user's set, or overwrite the one they have.

        One INSERT ... ON CONFLICT, so two concurrent generations both succeed and the later write wins.
        """
        now = dt.datetime.now(dt.UTC)
        values = {
            "generated_at": generated_at,
            "reference_month": reference_month,
            "month_to_date_through": month_to_date_through,
            "prompt_version": prompt_version,
            "insights": insights,
        }
        statement = insert(InsightSet).values(id=uuid7(), user_id=user_id, created_at=now, updated_at=now, **values)
        statement = statement.on_conflict_do_update(
            index_elements=[InsightSet.user_id], set_={**values, "updated_at": now}
        )
        await session.execute(statement)
        # populate_existing: a row already in the session must show the values just written.
        refreshed = select(InsightSet).where(InsightSet.user_id == user_id).execution_options(populate_existing=True)
        return (await session.execute(refreshed)).scalar_one()

    @staticmethod
    async def delete_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Remove the user's set, if any."""
        await session.execute(delete(InsightSet).where(InsightSet.user_id == user_id))


insight_repository = InsightRepository()
