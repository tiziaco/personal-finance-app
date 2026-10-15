"""The import's subscriptions to account events."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.modules.account import USER_ERASING
from app.modules.transaction.imports.service import import_service


@events.on(USER_ERASING, inline=True)
async def erase_imports_on_user_erasing(session: AsyncSession, user_id: uuid.UUID) -> None:
    """Permanently remove the user's remembered mappings and held upload.

    Inline, in the publishing transaction and before the user row is
    anonymised. A held upload is a bank statement; nothing references either
    table, so the rows go rather than being anonymised.
    """
    await import_service.delete_all_for_user(session, user_id)
