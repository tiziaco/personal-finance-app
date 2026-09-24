"""Set-based checkpoint deletion — the erasure path's half of the GDPR cascade."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.shared.checkpointing.postgres import (
    delete_conversation_checkpoints,
    delete_conversations_checkpoints,
)
from app.core.config import settings

pytestmark = pytest.mark.unit

TABLES = settings.database.CHECKPOINT_TABLES


@pytest.fixture
def pool_with_connection():
    """A stand-in for the psycopg pool, yielding a connection that records execute()."""
    conn = AsyncMock()
    pool = MagicMock()

    @asynccontextmanager
    async def connection():
        yield conn

    pool.connection = connection
    with patch(
        "app.agents.shared.checkpointing.postgres.create_connection_pool",
        new=AsyncMock(return_value=pool),
    ) as create_pool:
        yield create_pool, conn


class TestDeleteConversationsCheckpoints:
    async def test_one_statement_per_table_for_the_whole_set(self, pool_with_connection):
        _, conn = pool_with_connection

        await delete_conversations_checkpoints(["conv_1", "conv_2", "conv_3"])

        assert conn.execute.await_count == len(TABLES)
        for call, table in zip(conn.execute.await_args_list, TABLES, strict=True):
            sql, params = call.args
            assert table in sql
            assert "thread_id = ANY(" in sql
            assert params == (["conv_1", "conv_2", "conv_3"],)

    async def test_ids_are_bound_not_interpolated(self, pool_with_connection):
        _, conn = pool_with_connection

        await delete_conversations_checkpoints(["'; DROP TABLE checkpoints; --"])

        for call in conn.execute.await_args_list:
            sql, params = call.args
            assert "DROP TABLE" not in sql
            assert params == (["'; DROP TABLE checkpoints; --"],)

    async def test_empty_set_takes_no_connection(self, pool_with_connection):
        create_pool, conn = pool_with_connection

        await delete_conversations_checkpoints([])

        create_pool.assert_not_awaited()
        conn.execute.assert_not_awaited()


class TestDeleteConversationCheckpoints:
    async def test_singular_delegates_to_the_plural(self, pool_with_connection):
        _, conn = pool_with_connection

        await delete_conversation_checkpoints("conv_9")

        assert conn.execute.await_count == len(TABLES)
        assert conn.execute.await_args_list[0].args[1] == (["conv_9"],)
