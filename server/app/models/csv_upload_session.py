from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any, Dict, Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.user import User


class CSVUploadSession(BaseModel, table=True):
    """Short-lived session linking mapping_id to raw CSV bytes.

    Created in step 1 (upload), consumed in step 2 (confirm).
    TTL is controlled by settings.UPLOAD_SESSION_TTL_MINUTES.
    """

    __tablename__ = "csv_upload_session"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    mapping_id: str = Field(index=True, unique=True)   # UUID
    proposed_mapping: Dict[str, Any] = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    csv_content: str = Field(sa_column=sa.Column(sa.Text, nullable=False))  # raw UTF-8 CSV
    expires_at: datetime = Field(sa_type=sa.DateTime(timezone=True))

    user: Optional["User"] = Relationship()
