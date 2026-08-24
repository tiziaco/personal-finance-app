"""Base models and mixins for all models."""

from datetime import (
    UTC,
    datetime,
)
from typing import Optional

from sqlalchemy import (
    DateTime,
)
from sqlmodel import (
    Field,
    SQLModel,
)


class TimestampMixin(SQLModel):
    """Mixin for automatic timestamp tracking.
    
    Provides created_at and updated_at fields with automatic management:
    - created_at: Set once on creation
    - updated_at: Automatically updated on every modification
    """

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
        nullable=False,
        index=True,  # Often used in queries (recent records, date filters)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
        nullable=False,
        sa_column_kwargs={"onupdate": lambda: datetime.now(UTC)},
    )


class SoftDeleteMixin(SQLModel):
    """Mixin for soft delete functionality.
    
    ⚠️ GDPR WARNING: For B2C applications in Europe, soft deletes are NOT compliant
    with GDPR's "right to erasure" for user personal data. Use this mixin ONLY for:
    
    ✅ Appropriate use cases:
    - Internal admin/operational records (not user personal data)
    - Business records that must be retained for legal/tax compliance
    - Non-personal data (aggregated stats, system logs)
    - Accidental admin deletions (internal operations)
    
    ❌ DO NOT use for:
    - User accounts when user requests deletion (use hard delete + anonymization)
    - User personal data (name, email, etc.) - must be actually deleted
    - User-generated content when user requests deletion
    
    For GDPR-compliant user deletion, see AnonymizableMixin below.
    """

    deleted_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
        index=True,  # Queries often filter by deleted_at IS NULL
    )

    @property
    def is_deleted(self) -> bool:
        """Check if the record is soft deleted."""
        return self.deleted_at is not None

    def soft_delete(self) -> None:
        """Mark the record as deleted."""
        self.deleted_at = datetime.now(UTC)

    def restore(self) -> None:
        """Restore a soft deleted record."""
        self.deleted_at = None


class AnonymizableMixin(SQLModel):
    """Mixin for GDPR-compliant data anonymization.
    
    For B2C applications, when users request deletion, you should:
    1. Anonymize personal data (set to generic values)
    2. Keep the record ID for referential integrity
    3. Mark as anonymized with timestamp
    
    This allows you to:
    ✅ Comply with GDPR right to erasure
    ✅ Maintain business records for legal compliance
    ✅ Preserve data integrity (foreign keys remain valid)
    ✅ Keep non-personal analytics (e.g., "X conversations created")
    
    Use this for User accounts and other personal data models.
    """

    anonymized_at: Optional[datetime] = Field(
        default=None,
        sa_type=DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    @property
    def is_anonymized(self) -> bool:
        """Check if the record has been anonymized."""
        return self.anonymized_at is not None

    def mark_anonymized(self) -> None:
        """Mark the record as anonymized (after clearing personal data)."""
        self.anonymized_at = datetime.now(UTC)


class BaseModel(TimestampMixin, SQLModel):
    """Base model with timestamp tracking.
    
    All models should inherit from this to get automatic:
    - created_at timestamp
    - updated_at timestamp (auto-updated on modifications)
    
    For additional features, use:
    - SoftDeleteMixin: Add soft delete capability
    - AnonymizableMixin: Add GDPR-compliant anonymization for personal data
    """

    pass
