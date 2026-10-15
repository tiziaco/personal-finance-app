"""The migration history actually produces the models' schema.

Every other test builds its schema with `SQLModel.metadata.create_all`, which
reads the models, never the migrations — so a constraint or an `ondelete`
dropped from a revision alone would pass the rest of the suite. This runs
`alembic upgrade head` on a scratch database in the same test container and
diffs the result against `SQLModel.metadata`.

A plain, non-async test: `env.py` calls `asyncio.run()` itself, which would
collide with pytest-asyncio's loop.

`Config` is built without `alembic.ini`: `env.py` runs `fileConfig()` whenever
a config file is set, which resets the process's logging and disables every
logger already configured, for the rest of the session.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from pydantic import SecretStr
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlmodel import SQLModel

from alembic import command
from app.core.config import settings

pytestmark = pytest.mark.integration

ALEMBIC_SCRIPT_LOCATION = Path(__file__).resolve().parents[3] / "alembic"
SCRATCH_DB = "alembic_migration_check"

# Mirrors env.py's include_name: LangGraph creates these through setup(), never a migration.
EXCLUDED_TABLES = {"checkpoints", "checkpoint_blobs", "checkpoint_writes", "checkpoint_migrations"}


def _include_name(name, type_, parent_names) -> bool:
    if type_ == "table":
        return name not in EXCLUDED_TABLES
    return True


@contextmanager
def _scratch_database(test_database_url, monkeypatch) -> Iterator[tuple[Config, Engine]]:
    """An empty database in the test container, with alembic and an engine pointed at it; dropped after."""
    base_url = make_url(test_database_url)

    admin_conn = psycopg.connect(
        host=base_url.host,
        port=base_url.port,
        user=base_url.username,
        password=base_url.password,
        dbname=base_url.database,
        autocommit=True,
    )
    try:
        with admin_conn.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
            cur.execute(f'CREATE DATABASE "{SCRATCH_DB}"')

        # env.py builds its URL from settings.database, so this is how the upgrade reaches the scratch DB.
        monkeypatch.setattr(settings.database, "HOST", base_url.host)
        monkeypatch.setattr(settings.database, "PORT", base_url.port)
        monkeypatch.setattr(settings.database, "USER", base_url.username)
        monkeypatch.setattr(settings.database, "PASSWORD", SecretStr(base_url.password or ""))
        monkeypatch.setattr(settings.database, "DB", SCRATCH_DB)

        config = Config()
        config.set_main_option("script_location", str(ALEMBIC_SCRIPT_LOCATION))
        engine = create_engine(base_url.set(drivername="postgresql+psycopg", database=SCRATCH_DB))
        try:
            yield config, engine
        finally:
            engine.dispose()
    finally:
        with admin_conn.cursor() as cur:
            cur.execute(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}"')
        admin_conn.close()


def test_migrations_produce_the_models_schema(test_database_url, monkeypatch):
    """`alembic upgrade head` on an empty database == `SQLModel.metadata`."""
    with _scratch_database(test_database_url, monkeypatch) as (config, engine):
        command.upgrade(config, "head")
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection, opts={"include_name": _include_name, "compare_server_default": True}
            )
            diff = compare_metadata(context, SQLModel.metadata)

    assert diff == [], f"migrations produced a schema that disagrees with the models: {diff}"


def test_csv_import_revision_backfills_existing_rows(test_database_url, monkeypatch):
    """5b7e2c9d4f10: every row gets its merchant key; a recurring row from before is the user's (D6)."""
    user_id = uuid.uuid4()
    with _scratch_database(test_database_url, monkeypatch) as (config, engine):
        command.upgrade(config, "09aea922f9b1")
        with engine.begin() as conn:
            conn.execute(
                text(
                    'INSERT INTO "user" (id, clerk_id, email, email_verified, last_synced_at, created_at, updated_at)'
                    " VALUES (:id, 'clerk_backfill', 'backfill@example.com', true, now(), now(), now())"
                ),
                {"id": user_id},
            )
            for merchant, recurring, deleted in [
                ("PAYPAL *NETFLIX 4029357733", True, False),
                ("REWE Markt GmbH", False, False),
                ("Stadtwerke München", True, True),
            ]:
                conn.execute(
                    text(
                        'INSERT INTO "transaction" (id, user_id, created_at, updated_at, deleted_at, date, merchant,'
                        " amount, category, confidence, is_recurring, fingerprint) VALUES (:id, :user_id, now(),"
                        " now(), CASE WHEN :deleted THEN now() END, '2026-10-01', :merchant, -9.99, 'shopping',"
                        " 1.0, :recurring, :fp)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "user_id": user_id,
                        "deleted": deleted,
                        "merchant": merchant,
                        "recurring": recurring,
                        "fp": uuid.uuid4().hex * 2,
                    },
                )

        command.upgrade(config, "5b7e2c9d4f10")
        with engine.connect() as conn:
            rows = conn.execute(
                text('SELECT merchant, merchant_key, recurring_source FROM "transaction" ORDER BY merchant')
            ).all()

    assert [tuple(r) for r in rows] == [
        ("PAYPAL *NETFLIX 4029357733", "netflix", "user"),
        ("REWE Markt GmbH", "rewe markt", "detected"),
        ("Stadtwerke München", "stadtwerke münchen", "user"),
    ]
