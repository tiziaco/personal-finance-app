"""Subscriptions to account and transaction events."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.insights.service import insights_service
from app.modules.transaction import TRANSACTIONS_ALL_DELETED


@events.on(USER_ERASING, inline=True)
async def erase_on_user_erasing(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Permanently remove the user's insight set.

    Inline, in the publishing transaction and before the user row is
    anonymised. The insights quote the user's spending, so the row goes
    rather than being anonymised.
    """
    await insights_service.delete_for_user(session, user_id)


@events.on(TRANSACTIONS_ALL_DELETED, inline=True)
async def delete_on_all_transactions_deleted(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Drop the stored set: it quotes merchants and amounts from the rows just deleted.

    Inline, so the set cannot outlive the rows in a half-committed request.
    """
    await insights_service.delete_for_user(session, user_id)
