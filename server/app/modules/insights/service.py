"""Insights service: read the stored set with its freshness, or generate a new one."""

import datetime as dt
import uuid
from typing import Optional

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid_utils.compat import uuid7

from app.agents.core import InvalidModelAnswer
from app.agents.insights import PROMPT_VERSION, WrittenInsight, write_insights
from app.core.logging import logger
from app.database.dependencies import release_connection
from app.integrations.llm import LLMServiceError
from app.modules.insights.exceptions import InsightsUnavailableError
from app.modules.insights.figures import gather_figures
from app.modules.insights.models import InsightSet
from app.modules.insights.repository import insight_repository
from app.modules.insights.schemas import InsightResponse, InsightsResponse, InsightsStatus, StaleReason
from app.modules.transaction import transaction_service


def _today() -> dt.date:
    """Today's UTC date; a seam for tests."""
    return dt.datetime.now(dt.UTC).date()


def _response(row: InsightSet, status: InsightsStatus, stale_reason: Optional[StaleReason] = None) -> InsightsResponse:
    return InsightsResponse(
        status=status,
        stale_reason=stale_reason,
        generated_at=row.generated_at,
        reference_month=row.reference_month,
        month_to_date_through=row.month_to_date_through,
        insights=[InsightResponse.model_validate(item) for item in row.insights],
    )


def _to_response(item: WrittenInsight) -> InsightResponse:
    return InsightResponse.model_validate(item, from_attributes=True)


class InsightsService:
    """Reads never call the model; generate calls it once."""

    @staticmethod
    async def read(session: AsyncSession, user_id: uuid.UUID) -> InsightsResponse:
        """The stored set and its status. Stale when rows changed since it was written, or the month rolled over."""
        activity = await transaction_service.activity(session, user_id)
        if not activity.has_active:
            return InsightsResponse(status="no_data")
        row = await insight_repository.get(session, user_id)
        if row is None:
            return InsightsResponse(status="none")
        generated_at = row.generated_at.astimezone(dt.UTC)
        today = _today()
        changed = activity.last_changed_at is not None and activity.last_changed_at > row.generated_at
        rolled = (generated_at.year, generated_at.month) < (today.year, today.month)
        reason: Optional[StaleReason] = "new_month" if rolled else "data_changed" if changed else None
        try:
            return _response(row, "stale" if reason else "fresh", reason)
        except ValidationError:
            # Written to an earlier shape of the insight (a prompt change): the set is
            # unreadable now, so it counts as never written and the page writes a new one.
            logger.warning("insights_stored_set_unreadable", prompt_version=row.prompt_version)
            return InsightsResponse(status="none")

    @staticmethod
    async def generate(session: AsyncSession, user_id: uuid.UUID) -> InsightsResponse:
        """Write a new set from the user's figures and store it over the old one.

        The set is stamped with the moment its figures were read, not when the model answered: a transaction
        written while the model is thinking is newer than the set, which then reads stale. If every
        transaction went while it was thinking — erasure, or Settings' delete-all, both of which delete the
        stored set — nothing is stored: the set would quote the rows just removed.
        """
        started = dt.datetime.now(dt.UTC)
        figures = await gather_figures(session, user_id)
        if figures is None:
            return InsightsResponse(status="no_data")
        generation_id = uuid7()
        await release_connection(session)
        try:
            written = await write_insights(figures, user_id=user_id, generation_id=generation_id)
        except (InvalidModelAnswer, LLMServiceError) as e:
            logger.warning("insights_generation_failed", generation_id=str(generation_id), error=type(e).__name__)
            raise InsightsUnavailableError("Insights could not be generated", generation_id=str(generation_id)) from e
        if not (await transaction_service.activity(session, user_id)).has_active:
            return InsightsResponse(status="no_data")
        items = [_to_response(item) for item in written]
        row = await insight_repository.replace(
            session,
            user_id,
            generated_at=started,
            reference_month=figures.reference_month,
            month_to_date_through=figures.month_to_date_through,
            prompt_version=PROMPT_VERSION,
            insights=[item.model_dump(mode="json") for item in items],
        )
        return _response(row, "fresh")

    @staticmethod
    async def delete_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Remove everything the module stores for the user."""
        await insight_repository.delete_for_user(session, user_id)


insights_service = InsightsService()
