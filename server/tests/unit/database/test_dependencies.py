"""Pins for get_db_session's transaction boundary: commit after the route returns, before the response is sent."""

from typing import Any, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import IntegrityError

from app.database.dependencies import DbSession
from app.database.engine import create_session_factory
from app.exceptions.base import NotFoundError, ServiceError
from app.exceptions.handlers import service_exception_handler

pytestmark = pytest.mark.unit


class TestDeclaration:
    def test_the_session_dependency_is_function_scoped(self):
        """The whole fix is this keyword; the ordering tests below show what it buys."""
        assert DbSession.__metadata__[0].scope == "function"

    def test_the_session_factory_does_not_expire_on_commit(self):
        """chat_stream's generator reads conversation.id and user.id after the session has closed."""
        factory = create_session_factory(MagicMock())

        assert factory.kw["expire_on_commit"] is False


class _StubSession:
    """Just enough of AsyncSession for get_db_session's teardown, recording each call."""

    def __init__(self, events: list[str], fail_commit: bool = False) -> None:
        self.events = events
        self.fail_commit = fail_commit

    async def commit(self) -> None:
        self.events.append("commit")
        if self.fail_commit:
            raise IntegrityError("INSERT ...", {}, Exception("unique violation"))

    async def rollback(self) -> None:
        self.events.append("rollback")

    async def close(self) -> None:
        self.events.append("close")


async def _post(
    events: list[str],
    fail_commit: bool = False,
    fail_route: bool = False,
    route_error: Optional[Exception] = None,
    path: str = "/write",
) -> int:
    """POST to a throwaway app wired like the real one; record the first body frame in `events`."""
    app = FastAPI()
    app.state.session_factory = lambda: _StubSession(events, fail_commit)
    app.add_exception_handler(ServiceError, service_exception_handler)

    @app.post("/write")
    async def write(db_session: DbSession) -> dict[str, bool]:
        events.append("handler")
        if fail_route:
            raise NotFoundError("gone")
        if route_error is not None:
            raise route_error
        return {"ok": True}

    @app.post("/items/{item_id}")
    async def item(item_id: int, db_session: DbSession) -> dict[str, bool]:
        events.append("handler")
        return {"ok": True}

    async def probed(scope: dict[str, Any], receive: Any, send: Any) -> None:
        async def probed_send(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.body" and "body" not in events:
                events.append("body")
            await send(message)

        await app(scope, receive, probed_send)

    transport = ASGITransport(app=probed, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return (await client.post(path)).status_code


class TestOrdering:
    async def test_the_commit_lands_before_the_first_body_frame(self):
        """Under the default "request" scope the order is handler, body, commit: a 200 for an uncommitted write."""
        events: list[str] = []

        assert await _post(events) == 200
        assert events == ["handler", "commit", "close", "body"]

    async def test_a_failing_commit_answers_409_not_200(self):
        """A conflict found at commit time must reach the client, not follow a 200 already sent."""
        events: list[str] = []

        assert await _post(events, fail_commit=True) == 409
        assert events == ["handler", "commit", "rollback", "close", "body"]

    async def test_a_route_exception_rolls_back_without_committing(self):
        """The route's exception is thrown into get_db_session: rollback, never commit, then the error response."""
        events: list[str] = []

        assert await _post(events, fail_route=True) == 404
        assert events == ["handler", "rollback", "close", "body"]


def _session_errors(logger: MagicMock) -> list:
    return [c for c in logger.exception.call_args_list if c.args and c.args[0] == "database_session_error"]


class TestLogging:
    """database_session_error is for failures nothing else handles; a 4xx is not one."""

    async def test_a_handled_service_error_is_not_logged_as_a_session_error(self):
        events: list[str] = []

        with patch("app.database.dependencies.logger") as logger:
            assert await _post(events, fail_route=True) == 404

        assert _session_errors(logger) == []
        assert "rollback" in events

    async def test_a_validation_error_is_not_logged_as_a_session_error(self):
        events: list[str] = []

        with patch("app.database.dependencies.logger") as logger:
            assert await _post(events, path="/items/not-a-number") == 422

        assert _session_errors(logger) == []

    async def test_an_unexpected_exception_is_still_logged_with_its_traceback(self):
        events: list[str] = []

        with patch("app.database.dependencies.logger") as logger:
            assert await _post(events, route_error=RuntimeError("boom")) == 500

        assert len(_session_errors(logger)) == 1
        assert events == ["handler", "rollback", "close", "body"]
