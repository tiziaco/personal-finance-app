"""Supplier repository for database operations.

Scoped to contact linking. Supplier lifecycle (create/update/delete) arrives
with the first write route (architecture §9).
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.modules.supplier.models import Supplier


class SupplierRepository:
    """Repository for supplier database operations relevant to user/contact linking."""

    @staticmethod
    async def get_by_id(session: AsyncSession, supplier_id: str) -> Optional[Supplier]:
        """Get a supplier by internal ID.

        Args:
            session: Database session
            supplier_id: Supplier ID

        Returns:
            Supplier if found, None otherwise.
        """
        statement = select(Supplier).where(Supplier.id == supplier_id)
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_id_by_contact_id(session: AsyncSession, user_id: str) -> Optional[str]:
        """Get the id of the non-soft-deleted supplier linked to this user, if any.

        Args:
            session: Database session
            user_id: Local User.id (Supplier.contact_id)

        Returns:
            Supplier.id if a non-deleted supplier is linked, None otherwise.
        """
        statement = (
            select(Supplier.id).where(Supplier.contact_id == user_id).where(Supplier.deleted_at.is_(None)).limit(1)
        )
        result = await session.execute(statement)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_contact_id(session: AsyncSession, user_id: str) -> Optional[Supplier]:
        """Get the supplier (any deletion state) linked to this user's contact_id.

        Unlike get_id_by_contact_id, this is not scoped to non-deleted suppliers:
        used by GDPR erasure, which must clear the link unconditionally.

        Args:
            session: Database session
            user_id: Local User.id (Supplier.contact_id)

        Returns:
            Supplier if found, None otherwise.
        """
        statement = select(Supplier).where(Supplier.contact_id == user_id)
        result = await session.execute(statement)
        return result.scalars().first()

    @staticmethod
    async def set_contact_id(
        session: AsyncSession,
        supplier: Supplier,
        contact_id: Optional[str],
    ) -> Supplier:
        """Set Supplier.contact_id and flush.

        Pure DB write — no cache invalidation. Callers (SupplierService) own
        the previous_contact_id bookkeeping and cache invalidation side effects.

        Args:
            session: Database session
            supplier: The supplier to update
            contact_id: New contact_id (User.id), or None to unlink

        Returns:
            The updated Supplier.
        """
        supplier.contact_id = contact_id
        session.add(supplier)
        await session.flush()
        return supplier


supplier_repository = SupplierRepository()
