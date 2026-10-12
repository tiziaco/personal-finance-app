"""make user.org_id nullable for GDPR erasure.

anonymize_user() clears org_id, but the column was NOT NULL, so every call to
DELETE /api/v1/auth/me failed with a NotNullViolationError at commit — the
right-to-erasure endpoint had never completed successfully.

org_id is dropped on erasure rather than retained because a supplier
organisation typically has a single portal contact, so an anonymised record
carrying its org_id would still single that person out (Art 29 WP Opinion
05/2014 / EDPB Guidelines 04/2025 singling-out test).

Revision ID: b3f1c27a4e18
Revises: 0c7838405158
Create Date: 2026-08-25 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b3f1c27a4e18"
down_revision: Union[str, Sequence[str], None] = "0c7838405158"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        "user",
        "org_id",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema.

    Backfills a placeholder for already-anonymised rows, since they hold NULL
    and the restored constraint would otherwise reject them.
    """
    op.execute("UPDATE \"user\" SET org_id = '' WHERE org_id IS NULL")
    op.alter_column(
        "user",
        "org_id",
        existing_type=sqlmodel.sql.sqltypes.AutoString(),
        nullable=False,
    )
