"""The import's repository: held uploads and remembered mappings, each query scoped by user_id."""

import uuid
from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from uuid_utils.compat import uuid7

from app.core.logging import logger
from app.modules.transaction.imports.models import HeldUpload, MappingProfile


class ImportRepository:
    """Repository for the import's tables."""

    @staticmethod
    async def replace_upload(
        session: AsyncSession, user_id: uuid.UUID, content: str, expires_at: datetime
    ) -> HeldUpload:
        """Hold a new upload for this user, replacing any held before: one per user (D9)."""
        now = datetime.now(UTC)
        statement = (
            insert(HeldUpload)
            .values(
                id=uuid.uuid4(),
                user_id=user_id,
                content=content,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                constraint="uq_csv_upload_user_id",
                # A new id each time: a confirm against the replaced upload's id is a 404.
                set_={"id": uuid.uuid4(), "content": content, "expires_at": expires_at, "updated_at": now},
            )
            .returning(HeldUpload)
        )
        upload = (await session.execute(statement)).scalar_one()
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
    async def take_upload(session: AsyncSession, user_id: uuid.UUID, upload_id: uuid.UUID) -> bool:
        """Delete this user's held upload; False when it is already gone.

        The row lock is the double-confirm guard: a second confirm's DELETE waits
        for the first to commit, then finds nothing.
        """
        statement = (
            delete(HeldUpload)
            .where(HeldUpload.id == upload_id, HeldUpload.user_id == user_id)
            .returning(HeldUpload.id)
        )
        return (await session.execute(statement)).scalar_one_or_none() is not None

    @staticmethod
    async def put_profile(session: AsyncSession, user_id: uuid.UUID, column_key: str, mapping: dict[str, str]) -> None:
        """Remember a confirmed mapping for this column set, replacing the one remembered before."""
        now = datetime.now(UTC)
        statement = (
            insert(MappingProfile)
            .values(
                id=uuid7(), user_id=user_id, column_key=column_key, mapping=mapping, created_at=now, updated_at=now
            )
            .on_conflict_do_update(
                constraint="uq_csv_mapping_profile_user_id_column_key", set_={"mapping": mapping, "updated_at": now}
            )
        )
        await session.execute(statement)
        await session.flush()

    @staticmethod
    async def delete_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
        """Permanently remove the user's remembered mappings and held upload."""
        profiles = await session.execute(delete(MappingProfile).where(MappingProfile.user_id == user_id))
        uploads = await session.execute(delete(HeldUpload).where(HeldUpload.user_id == user_id))
        logger.info("csv_import_data_deleted", user_id=user_id, profiles=profiles.rowcount, uploads=uploads.rowcount)


import_repository = ImportRepository()
