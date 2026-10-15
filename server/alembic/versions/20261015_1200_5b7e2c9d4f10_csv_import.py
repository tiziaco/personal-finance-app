"""csv import: merchant key, recurring source, mapping profiles, held uploads.

Revision ID: 5b7e2c9d4f10
Revises: 09aea922f9b1
Create Date: 2026-10-15 12:00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql

from alembic import op

# The live normaliser, not a frozen copy: changing it changes stored keys, which needs
# its own backfill revision whatever this one does (docs/data-model/transaction.md, D7).
from app.modules.transaction.domain import normalise_merchant

revision: str = "5b7e2c9d4f10"
down_revision: Union[str, Sequence[str], None] = "09aea922f9b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "transaction", sa.Column("merchant_key", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True)
    )
    # A server default only to fill existing rows; the app sets every value after this.
    op.add_column(
        "transaction",
        sa.Column(
            "recurring_source", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=False, server_default="detected"
        ),
    )
    op.alter_column("transaction", "recurring_source", server_default=None)
    conn = op.get_bind()
    for merchant in conn.execute(sa.text('SELECT DISTINCT merchant FROM "transaction"')).scalars().all():
        conn.execute(
            sa.text('UPDATE "transaction" SET merchant_key = :key WHERE merchant = :merchant'),
            {"key": normalise_merchant(merchant), "merchant": merchant},
        )
    op.alter_column("transaction", "merchant_key", nullable=False)
    op.create_index("ix_transaction_user_id_merchant_key", "transaction", ["user_id", "merchant_key"], unique=False)

    op.create_table(
        "csv_mapping_profile",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("column_key", sa.CHAR(length=64), nullable=False),
        sa.Column("mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "column_key", name="uq_csv_mapping_profile_user_id_column_key"),
    )
    op.create_index(op.f("ix_csv_mapping_profile_created_at"), "csv_mapping_profile", ["created_at"], unique=False)
    op.create_index(op.f("ix_csv_mapping_profile_user_id"), "csv_mapping_profile", ["user_id"], unique=False)

    op.create_table(
        "csv_upload",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), server_default=sa.text("uuidv7()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_csv_upload_user_id"),
    )
    op.create_index(op.f("ix_csv_upload_created_at"), "csv_upload", ["created_at"], unique=False)
    op.create_index(op.f("ix_csv_upload_user_id"), "csv_upload", ["user_id"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_csv_upload_user_id"), table_name="csv_upload")
    op.drop_index(op.f("ix_csv_upload_created_at"), table_name="csv_upload")
    op.drop_table("csv_upload")
    op.drop_index(op.f("ix_csv_mapping_profile_user_id"), table_name="csv_mapping_profile")
    op.drop_index(op.f("ix_csv_mapping_profile_created_at"), table_name="csv_mapping_profile")
    op.drop_table("csv_mapping_profile")
    op.drop_index("ix_transaction_user_id_merchant_key", table_name="transaction")
    op.drop_column("transaction", "recurring_source")
    op.drop_column("transaction", "merchant_key")
