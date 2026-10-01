"""Supplier service — the contact link between a supplier and a portal user."""

import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.modules.supplier.cache import supplier_cache
from app.modules.supplier.repository import supplier_repository
from app.utils.cache import MISS


class SupplierService:
    """Links, unlinks and resolves the supplier a user manages."""

    @staticmethod
    async def link_from_metadata(session: AsyncSession, user_id: uuid.UUID, metadata: dict) -> Optional[uuid.UUID]:
        """Link a supplier to this user based on invitation metadata.

        Runs on every account sync (JIT provisioning and two webhooks), so it
        must be safely repeatable. Only an unlinked supplier is claimed, unless
        the metadata carries a truthy `replace` flag — so a retried event, or a
        second invite for an already-linked supplier, changes nothing.

        Args:
            session: DB session. Flushed, not committed.
            user_id: The user to link.
            metadata: Merged public metadata; read for `supplier_id` and `replace`.

        Returns:
            The linked Supplier.id, or None if nothing was linked.
        """
        raw_supplier_id = metadata.get("supplier_id")
        if not raw_supplier_id:
            return None
        try:
            supplier_id = uuid.UUID(str(raw_supplier_id))
        except ValueError:
            logger.warning("supplier_link_target_missing", supplier_id=raw_supplier_id, user_id=user_id)
            return None

        replace_flag = bool(metadata.get("replace"))

        supplier = await supplier_repository.get_by_id(session, supplier_id)
        if supplier is None:
            logger.warning("supplier_link_target_missing", supplier_id=supplier_id, user_id=user_id)
            return None
        if supplier.contact_id is not None and not replace_flag:
            return None

        # Capture BEFORE overwriting. With replace_flag this is a RE-LINK: the
        # displaced contact holds a cached user_id -> supplier_id entry that is
        # now wrong, and once the old id is gone that entry is unreachable.
        previous_contact_id = supplier.contact_id
        supplier = await supplier_repository.set_contact_id(session, supplier, user_id)

        if previous_contact_id and previous_contact_id != user_id:
            await supplier_cache.invalidate_user(user_id=previous_contact_id)
        await supplier_cache.invalidate_user(user_id=user_id)

        logger.info(
            "supplier_linked",
            supplier_id=supplier.id,
            user_id=user_id,
            previous_contact_id=previous_contact_id,
            replace=replace_flag,
        )
        return supplier.id

    @staticmethod
    async def unlink_contact(session: AsyncSession, user_id: uuid.UUID) -> Optional[uuid.UUID]:
        """Clear Supplier.contact_id for any supplier this user manages.

        Anonymising the user row leaves Supplier.contact_id pointing at it,
        which still records *which supplier this person managed*. Clearing it
        removes that association; the supplier is left contact-less until
        someone is re-invited to it.

        Args:
            session: DB session. Flushed, not committed.
            user_id: Local User.id.

        Returns:
            The unlinked Supplier.id, or None if the user managed no supplier.
        """
        supplier = await supplier_repository.get_by_contact_id(session, user_id)
        if supplier is None:
            return None

        supplier = await supplier_repository.set_contact_id(session, supplier, None)
        await supplier_cache.invalidate_user(user_id=user_id)
        logger.info("supplier_unlinked", supplier_id=supplier.id, user_id=user_id)
        return supplier.id

    @staticmethod
    async def get_id_for_user(session: AsyncSession, user_id: uuid.UUID) -> Optional[uuid.UUID]:
        """Resolve the Supplier.id linked to this user, cache-first.

        A cached None is honoured as "known not linked" rather than treated as
        a miss. Returns None if no (non-soft-deleted) supplier is linked.
        """
        cached = await supplier_cache.get_supplier_id(user_id)
        if cached is not MISS:
            return cached

        supplier_id = await supplier_repository.get_id_by_contact_id(session, user_id)
        await supplier_cache.set_supplier_id(user_id, supplier_id)
        return supplier_id


supplier_service = SupplierService()
