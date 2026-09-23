"""Subscriptions to account events.

All three are inline (architecture §5): a supplier's first request JIT-provisions
the user and resolves SupplierID in one transaction, so the link must exist
before the publisher commits; and an anonymised user row that still has a
Supplier.contact_id pointing at it is the association erasure exists to remove.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import events
from app.core.logging import logger
from app.modules.account import USER_ERASING, USER_OFFBOARDED, USER_SYNCED
from app.modules.supplier.cache import supplier_cache
from app.modules.supplier.service import supplier_service


@events.on(USER_SYNCED, inline=True)
async def link_on_user_synced(session: AsyncSession, user_id: str, metadata: dict) -> None:
    """Claim the supplier named in the invitation metadata, if any."""
    await supplier_service.link_from_metadata(session, user_id, metadata)


@events.on(USER_ERASING, inline=True)
async def unlink_on_user_erasing(session: AsyncSession, user_id: str) -> None:
    """Drop the contact link and the cached link; the user is about to be anonymised."""
    await supplier_service.unlink_contact(session, user_id)
    await supplier_cache.invalidate_user(user_id=user_id)


@events.on(USER_OFFBOARDED, inline=True)
async def unlink_on_user_offboarded(session: AsyncSession, user_id: str) -> None:
    """Drop the contact link when the user leaves their organisation.

    Leaves the supplier contact-less with no signal to a project manager
    beyond this log line — a known cost, recorded in the webhooks design spec.
    """
    supplier_id = await supplier_service.unlink_contact(session, user_id)
    await supplier_cache.invalidate_user(user_id=user_id)
    if supplier_id is not None:
        logger.info("supplier_unlinked_on_offboarding", user_id=user_id, supplier_id=supplier_id)
