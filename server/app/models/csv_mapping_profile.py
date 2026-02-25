from datetime import UTC, datetime
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlmodel import Field, Relationship

from app.models.base import BaseModel

if False:  # TYPE_CHECKING
    from app.models.user import User


class CSVMappingProfile(BaseModel, table=True):
    """Stores the column→field mapping for a user's CSV format.

    Keyed by (user_id, column_hash) so one profile is stored per unique
    set of CSV column names. Supports users importing from multiple banks.
    """

    __tablename__ = "csv_mapping_profile"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    column_hash: str = Field(index=True)      # SHA-256 of sorted frozenset of column names
    mapping: Dict[str, Any] = Field(sa_column=sa.Column(sa.JSON, nullable=False))
    last_used_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=sa.DateTime(timezone=True),
    )

    user: Optional["User"] = Relationship()
