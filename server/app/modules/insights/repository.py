"""Insight repository: every query, each one scoped by user_id."""

import datetime as dt
import uuid
from typing import Any, Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

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
        baseline_months: int,
        month_to_date_through: Optional[dt.date],
        prompt_version: str,
        insights: list[dict[str, Any]],
    ) -> InsightSet:
        """Insert the user's set, or overwrite the one they have."""
        row = await InsightRepository.get(session, user_id)
        if row is None:
            row = InsightSet(user_id=user_id, **_fields(locals()))
            session.add(row)
        else:
            for name, value in _fields(locals()).items():
                setattr(row, name, value)
        await session.flush()
        await session.refresh(row)
        return row

    @staticmethod
    async def delete_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Remove the user's set, if any."""
        await session.execute(delete(InsightSet).where(InsightSet.user_id == user_id))


def _fields(local_vars: dict[str, Any]) -> dict[str, Any]:
    """The replaceable columns, picked out of replace()'s locals."""
    names = (
        "generated_at",
        "reference_month",
        "baseline_months",
        "month_to_date_through",
        "prompt_version",
        "insights",
    )
    return {name: local_vars[name] for name in names}


insight_repository = InsightRepository()
