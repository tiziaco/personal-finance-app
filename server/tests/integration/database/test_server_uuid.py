"""The database provides uuidv7() — PostgreSQL 18 or later. Every primary key's server default calls it."""

import uuid

import pytest
from sqlalchemy import text

pytestmark = pytest.mark.integration


async def test_the_database_generates_uuid_v7(db_session):
    value = (await db_session.execute(text("SELECT uuidv7()"))).scalar_one()

    assert isinstance(value, uuid.UUID)
    assert value.version == 7


async def test_server_side_v7_ids_are_time_ordered(db_session):
    rows = (await db_session.execute(text("SELECT uuidv7() FROM generate_series(1, 50)"))).scalars().all()

    assert rows == sorted(rows)


async def test_a_row_inserted_without_an_id_gets_a_v7(db_session):
    """Raw SQL and seed scripts skip the app-side default; the server default covers them."""
    result = await db_session.execute(
        text(
            'INSERT INTO "user" (clerk_id, email, email_verified, created_at, updated_at, last_synced_at) '
            "VALUES ('clerk_raw_insert', 'raw_insert@example.com', false, now(), now(), now()) RETURNING id"
        )
    )

    assert result.scalar_one().version == 7
