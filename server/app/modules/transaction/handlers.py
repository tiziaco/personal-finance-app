"""Subscriptions to account events."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.transaction.service import transaction_service


@events.on(USER_ERASING, inline=True)
async def erase_on_user_erasing(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Permanently remove every transaction the user owns, soft-deleted ones included.

    Inline, in the publishing transaction and before the user row is
    anonymised. Merchants, amounts and descriptions are personal financial
    data; nothing references a transaction, so the rows go rather than being
    anonymised (docs/data-model/transaction.md).
    """
    await transaction_service.delete_all_for_user(session, user_id)
