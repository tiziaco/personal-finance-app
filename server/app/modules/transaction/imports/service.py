"""The import: upload a bank's CSV, review its mapping, confirm (docs/product/features/csv-import.md)."""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.transaction.imports.repository import import_repository


class ImportService:
    """Orchestrates the import."""

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Erasure: the user's remembered mappings and held upload."""
        await import_repository.delete_all_for_user(session, user_id)


import_service = ImportService()
