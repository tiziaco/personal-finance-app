"""The import's repository: held uploads and remembered mappings, each query scoped by user_id."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.logging import logger
from app.modules.transaction.imports.models import HeldUpload, MappingProfile


class ImportRepository:
    """Repository for the import's tables."""

    @staticmethod
    async def replace_upload(
        session: AsyncSession, user_id: uuid.UUID, content: str, expires_at: datetime
    ) -> HeldUpload:
        """Hold a new upload for this user, replacing any held before: one per user (D9)."""
        await session.execute(delete(HeldUpload).where(HeldUpload.user_id == user_id))
        upload = HeldUpload(user_id=user_id, content=content, expires_at=expires_at)
        session.add(upload)
        await session.flush()
        logger.info("csv_upload_held", user_id=user_id, upload_id=upload.id)
        return upload

    @staticmethod
    async def get_live_upload(
        session: AsyncSession, user_id: uuid.UUID, upload_id: uuid.UUID, now: datetime
    ) -> Optional[HeldUpload]:
        """This user's held upload if it has not expired, else None."""
        statement = select(HeldUpload).where(
            HeldUpload.id == upload_id, HeldUpload.user_id == user_id, HeldUpload.expires_at > now
        )
        return (await session.execute(statement)).scalar_one_or_none()

    @staticmethod
    async def get_profile(session: AsyncSession, user_id: uuid.UUID, column_key: str) -> Optional[MappingProfile]:
        """This user's remembered mapping for a column set, or None."""
        statement = select(MappingProfile).where(
            MappingProfile.user_id == user_id, MappingProfile.column_key == column_key
        )
        return (await session.execute(statement)).scalar_one_or_none()

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Permanently remove the user's remembered mappings and held upload."""
        profiles = await session.execute(delete(MappingProfile).where(MappingProfile.user_id == user_id))
        uploads = await session.execute(delete(HeldUpload).where(HeldUpload.user_id == user_id))
        logger.info("csv_import_data_deleted", user_id=user_id, profiles=profiles.rowcount, uploads=uploads.rowcount)


import_repository = ImportRepository()
