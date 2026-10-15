"""The import's repository: held uploads and remembered mappings, each query scoped by user_id."""

import uuid

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.modules.transaction.imports.models import HeldUpload, MappingProfile


class ImportRepository:
    """Repository for the import's tables."""

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Permanently remove the user's remembered mappings and held upload."""
        profiles = await session.execute(delete(MappingProfile).where(MappingProfile.user_id == user_id))
        uploads = await session.execute(delete(HeldUpload).where(HeldUpload.user_id == user_id))
        logger.info("csv_import_data_deleted", user_id=user_id, profiles=profiles.rowcount, uploads=uploads.rowcount)


import_repository = ImportRepository()
