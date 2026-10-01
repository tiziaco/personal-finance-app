"""The user row and the organisation roles."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import Field

from app.models.base import AnonymizableMixin, BaseModel, UUIDPrimaryKeyMixin


class User(BaseModel, UUIDPrimaryKeyMixin, AnonymizableMixin, table=True):
    """User model for storing user accounts.

    GDPR Compliance:
    - When user requests deletion, publish USER_ERASING (see UserService.erase_user)
      for the complete cascade. anonymize_user() alone clears only this row —
      conversation names and other modules' PII are cleared by their own
      USER_ERASING subscribers
    - Keep the record ID for referential integrity (conversations, etc.)
    - Mark with anonymized_at timestamp

    Attributes:
        id: UUID v7 primary key (UUIDPrimaryKeyMixin)
        clerk_id: External Clerk user ID for auth lookups (anonymized on deletion)
        org_id: Clerk organisation ID. Set from JWT on every login; used for
            tenant-scoped DB queries. Intentionally not the role (see design spec).
            Nullable because GDPR erasure clears it: a supplier organisation
            typically has a single portal contact, so retaining it on an
            anonymised record would still single that person out.
        email: User's email address (anonymized on deletion)
        email_verified: Whether the email is verified in Clerk
        first_name: User's first name from Clerk (anonymized on deletion)
        last_name: User's last name from Clerk (anonymized on deletion)
        avatar_url: User's avatar URL from Clerk (anonymized on deletion)
        last_synced_at: Last time data was synced from Clerk
        created_at: When the user was created (from BaseModel)
        updated_at: Last time the record was updated (auto-managed by BaseModel)
        anonymized_at: When personal data was anonymized (GDPR deletion)
    """

    clerk_id: str = Field(unique=True, index=True)
    org_id: Optional[str] = Field(default=None, index=True)
    email: str = Field(unique=True, index=True)
    email_verified: bool = Field(default=False)
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)
    last_synced_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
        nullable=False,
    )

    def anonymize_user(self) -> None:
        """Blank this row's own PII fields for GDPR compliance.

        Only this table — conversation names and other modules' PII are
        cleared by their own USER_ERASING subscribers. Call through
        UserService.erase_user (which publishes USER_ERASING), not directly:
        alone, this leaves conversation names unerased.
        """
        anonymous_id = f"deleted_user_{self.id}"
        self.clerk_id = anonymous_id
        self.email = f"{anonymous_id}@anonymized.local"
        self.email_verified = False
        self.first_name = None
        self.last_name = None
        self.avatar_url = None
        self.org_id = None

        self.mark_anonymized()


class Role(StrEnum):
    """Clerk organisation roles.

    Values match the Clerk org role slugs with the 'org:' prefix stripped.
    The AuthMiddleware extracts org_role from the JWT and strips the prefix
    before storing it in request.state.org_role.

    Migration note: when switching auth providers, only AuthMiddleware changes.
    This enum and all consumers remain unchanged.
    """

    PROJECT_MANAGER = "project_manager"
    REVIEWER = "reviewer"
    APPROVER = "approver"
    SUPPLIER = "supplier"
