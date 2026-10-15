"""The import's tables: remembered mappings and the held upload (docs/data-model/transaction.md, D8–D9).

Both are user-owned and hard-deleted on erasure; nothing references them. Their
class names are two words, so they set `__tablename__` in snake_case — SQLModel's
default would be `mappingprofile`.
"""

from datetime import datetime

from sqlalchemy import CHAR, Column, DateTime, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models.base import BaseModel, UserOwnedMixin, UUIDPrimaryKeyMixin


class MappingProfile(BaseModel, UUIDPrimaryKeyMixin, UserOwnedMixin, table=True):
    """A confirmed column mapping, remembered for the next file with the same set of column names."""

    __tablename__ = "csv_mapping_profile"
    __table_args__ = (UniqueConstraint("user_id", "column_key", name="uq_csv_mapping_profile_user_id_column_key"),)

    column_key: str = Field(sa_column=Column(CHAR(64), nullable=False))
    mapping: dict[str, str] = Field(sa_column=Column(JSONB, nullable=False))


class HeldUpload(BaseModel, UUIDPrimaryKeyMixin, UserOwnedMixin, table=True):
    """An uploaded file waiting for its confirm: one per user, for 30 minutes."""

    __tablename__ = "csv_upload"
    __table_args__ = (UniqueConstraint("user_id", name="uq_csv_upload_user_id"),)

    content: str = Field(sa_column=Column(Text, nullable=False))
    expires_at: datetime = Field(sa_type=DateTime(timezone=True), nullable=False)
