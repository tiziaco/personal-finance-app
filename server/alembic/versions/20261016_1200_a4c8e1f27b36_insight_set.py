"""insight_set: a user's latest AI insights.

Revision ID: a4c8e1f27b36
Revises: 5b7e2c9d4f10
Create Date: 2026-10-16 12:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a4c8e1f27b36"
down_revision: Union[str, Sequence[str], None] = "5b7e2c9d4f10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "insight_set",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reference_month", sqlmodel.sql.sqltypes.AutoString(length=7), nullable=False),
        sa.Column("month_to_date_through", sa.Date(), nullable=True),
        sa.Column("prompt_version", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False),
        sa.Column("insights", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["user.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_insight_set_created_at"), "insight_set", ["created_at"], unique=False)
    op.create_index(op.f("ix_insight_set_user_id"), "insight_set", ["user_id"], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_insight_set_user_id"), table_name="insight_set")
    op.drop_index(op.f("ix_insight_set_created_at"), table_name="insight_set")
    op.drop_table("insight_set")
