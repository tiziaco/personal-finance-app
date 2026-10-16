"""Subscriptions to account events."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.insights.service import insights_service


@events.on(USER_ERASING, inline=True)
async def erase_on_user_erasing(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Permanently remove the user's insight set.

    Inline, in the publishing transaction and before the user row is
    anonymised. The insights quote the user's spending, so the row goes
    rather than being anonymised.
    """
    await insights_service.delete_for_user(session, user_id)
