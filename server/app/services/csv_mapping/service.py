"""Service for CSV upload sessions and column mapping profiles."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import settings
from app.core.logging import logger
from app.models.csv_mapping_profile import CSVMappingProfile
from app.models.csv_upload_session import CSVUploadSession


class CSVMappingService:
    """Stateless service for CSV upload sessions and column mapping profiles."""

    @staticmethod
    def compute_column_hash(columns: list[str]) -> str:
        """SHA-256 of the sorted column names — order-independent fingerprint."""
        return hashlib.sha256("|".join(sorted(columns)).encode()).hexdigest()

    @staticmethod
    async def get_profile(
        db: AsyncSession,
        user_id: str,
        column_hash: str,
    ) -> Optional[CSVMappingProfile]:
        """Return the mapping profile for this user+column set, or None."""
        stmt = select(CSVMappingProfile).where(
            CSVMappingProfile.user_id == user_id,
            CSVMappingProfile.column_hash == column_hash,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def save_profile(
        db: AsyncSession,
        user_id: str,
        column_hash: str,
        mapping: Dict[str, Any],
    ) -> CSVMappingProfile:
        """Create or update a mapping profile for this user+column set."""
        stmt = select(CSVMappingProfile).where(
            CSVMappingProfile.user_id == user_id,
            CSVMappingProfile.column_hash == column_hash,
        )
        result = await db.execute(stmt)
        profile = result.scalar_one_or_none()

        if profile:
            profile.mapping = mapping
            profile.last_used_at = datetime.now(UTC)
        else:
            profile = CSVMappingProfile(
                user_id=user_id,
                column_hash=column_hash,
                mapping=mapping,
                last_used_at=datetime.now(UTC),
            )

        db.add(profile)
        await db.flush()
        await db.refresh(profile)

        logger.info("csv_mapping_profile_saved", user_id=user_id, column_hash=column_hash)
        return profile

    @staticmethod
    async def create_session(
        db: AsyncSession,
        user_id: str,
        proposed_mapping: Dict[str, Any],
        csv_content: str,
    ) -> CSVUploadSession:
        """Create a new upload session with a fresh UUID mapping_id."""
        mapping_id = str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(
            minutes=settings.UPLOAD_SESSION_TTL_MINUTES
        )
        session = CSVUploadSession(
            user_id=user_id,
            mapping_id=mapping_id,
            proposed_mapping=proposed_mapping,
            csv_content=csv_content,
            expires_at=expires_at,
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)

        logger.info("csv_upload_session_created", user_id=user_id, mapping_id=mapping_id)
        return session

    @staticmethod
    async def get_session(
        db: AsyncSession,
        mapping_id: str,
        user_id: str,
    ) -> Optional[CSVUploadSession]:
        """Return the session if it exists, belongs to the user, and has not expired."""
        stmt = select(CSVUploadSession).where(
            CSVUploadSession.mapping_id == mapping_id,
            CSVUploadSession.user_id == user_id,
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()

        if session is None:
            return None

        if session.expires_at < datetime.now(UTC):
            logger.info("csv_upload_session_expired", mapping_id=mapping_id)
            return None

        return session

    @staticmethod
    async def expire_session(db: AsyncSession, session: CSVUploadSession) -> None:
        """Immediately expire a session after it has been consumed."""
        session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.add(session)
        await db.flush()
