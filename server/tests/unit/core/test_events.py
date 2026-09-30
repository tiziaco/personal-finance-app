"""Tests for the in-process event dispatcher (architecture §8)."""

from unittest.mock import AsyncMock, patch

import pytest

import app.core.events as events_module
from app.core.events import EventDispatcher

pytestmark = pytest.mark.unit


class FakeSession:
    """The subset of AsyncSession a deferred handler's context manager needs."""

    def __init__(self) -> None:
        self.committed = False

    async def __aenter__(self) -> "FakeSession":
        return self

    async def __aexit__(self, *exc) -> bool:
        return False

    async def commit(self) -> None:
        self.committed = True


class FakeSessionFactory:
    def __init__(self) -> None:
        self.sessions: list[FakeSession] = []

    def __call__(self) -> FakeSession:
        session = FakeSession()
        self.sessions.append(session)
        return session


async def test_publish_with_no_subscribers_returns_zero():
    dispatcher = EventDispatcher()
    assert await dispatcher.publish("nothing.happened", key="value") == 0


async def test_inline_handler_runs_at_publish_with_the_full_payload():
    dispatcher = EventDispatcher()
    handler = AsyncMock()
    dispatcher.subscribe("thing.done", handler, inline=True)

    count = await dispatcher.publish("thing.done", session="s", user_id="u1")

    handler.assert_awaited_once_with(session="s", user_id="u1")
    assert count == 1


async def test_inline_handlers_run_in_registration_order():
    dispatcher = EventDispatcher()
    order: list[str] = []

    @dispatcher.on("thing.done", inline=True)
    async def first(**_):
        order.append("first")

    @dispatcher.on("thing.done", inline=True)
    async def second(**_):
        order.append("second")

    await dispatcher.publish("thing.done")
    assert order == ["first", "second"]


async def test_inline_handler_exception_propagates_and_stops_the_sequence():
    dispatcher = EventDispatcher()
    second = AsyncMock()

    @dispatcher.on("thing.done", inline=True)
    async def first(**_):
        raise RuntimeError("boom")

    dispatcher.subscribe("thing.done", second, inline=True)

    with pytest.raises(RuntimeError, match="boom"):
        await dispatcher.publish("thing.done")
    second.assert_not_awaited()


def test_on_returns_the_handler_unchanged_and_lists_it():
    dispatcher = EventDispatcher()

    async def handler(**_):
        pass

    assert dispatcher.on("x")(handler) is handler
    assert dispatcher.handlers("x") == (handler,)


async def test_events_are_isolated_by_name():
    dispatcher = EventDispatcher()
    handler = AsyncMock()
    dispatcher.subscribe("a", handler, inline=True)
    await dispatcher.publish("b")
    handler.assert_not_awaited()


async def test_deferred_handler_is_queued_not_run_and_counted():
    dispatcher = EventDispatcher()
    handler = AsyncMock()
    dispatcher.subscribe("order.placed", handler)  # deferred is the default

    count = await dispatcher.publish("order.placed", session="publisher", order_id="o1")

    handler.assert_not_awaited()
    assert count == 1


async def test_flush_runs_deferred_handlers_with_their_own_session_and_no_publisher_session():
    dispatcher = EventDispatcher()
    handler = AsyncMock()
    dispatcher.subscribe("order.placed", handler)
    factory = FakeSessionFactory()
    await dispatcher.publish("order.placed", session="publisher", order_id="o1")

    ran = await dispatcher.flush(factory)

    assert ran == 1
    assert len(factory.sessions) == 1
    handler.assert_awaited_once_with(session=factory.sessions[0], order_id="o1")
    assert factory.sessions[0].committed is True


async def test_flush_empties_the_queue():
    dispatcher = EventDispatcher()
    dispatcher.subscribe("order.placed", AsyncMock())
    factory = FakeSessionFactory()
    await dispatcher.publish("order.placed", order_id="o1")

    assert await dispatcher.flush(factory) == 1
    assert await dispatcher.flush(factory) == 0
    assert len(factory.sessions) == 1


async def test_flush_on_an_empty_queue_is_a_noop():
    dispatcher = EventDispatcher()
    factory = FakeSessionFactory()
    assert await dispatcher.flush(factory) == 0
    assert factory.sessions == []


async def test_failing_deferred_handler_is_logged_counted_and_does_not_stop_the_others():
    dispatcher = EventDispatcher()
    second = AsyncMock()

    @dispatcher.on("order.placed")
    async def first(**_):
        raise RuntimeError("boom")

    dispatcher.subscribe("order.placed", second)
    factory = FakeSessionFactory()
    await dispatcher.publish("order.placed", order_id="o1")

    with (
        patch("app.core.events.logger") as logger,
        patch("app.core.events.app_event_handler_failures_total") as counter,
    ):
        ran = await dispatcher.flush(factory)

    assert ran == 2
    second.assert_awaited_once()
    logger.exception.assert_called_once()
    assert logger.exception.call_args.args[0] == "event_handler_failed"
    assert logger.exception.call_args.kwargs["event_name"] == "order.placed"
    assert logger.exception.call_args.kwargs["handler"].endswith("first")
    counter.labels.assert_called_once_with(event="order.placed", handler=logger.exception.call_args.kwargs["handler"])
    counter.labels.return_value.inc.assert_called_once()


async def test_begin_discards_whatever_was_queued_before():
    dispatcher = EventDispatcher()
    handler = AsyncMock()
    dispatcher.subscribe("order.placed", handler)
    await dispatcher.publish("order.placed", order_id="stale")

    dispatcher.begin()

    assert await dispatcher.flush(FakeSessionFactory()) == 0
    handler.assert_not_awaited()


async def test_inline_and_deferred_subscribers_of_one_event_both_count():
    dispatcher = EventDispatcher()
    inline = AsyncMock()
    deferred = AsyncMock()
    dispatcher.subscribe("thing.done", inline, inline=True)
    dispatcher.subscribe("thing.done", deferred)

    count = await dispatcher.publish("thing.done", session="s")

    assert count == 2
    inline.assert_awaited_once_with(session="s")
    deferred.assert_not_awaited()


async def test_flush_drains_an_event_published_by_a_deferred_handler():
    """A deferred handler that publishes a second deferred event must not lose it."""
    dispatcher = EventDispatcher()
    second_handler = AsyncMock()

    async def first_handler(session, **_):
        await dispatcher.publish("second.event", session=session)

    dispatcher.subscribe("first.event", first_handler)
    dispatcher.subscribe("second.event", second_handler)
    factory = FakeSessionFactory()
    await dispatcher.publish("first.event")

    ran = await dispatcher.flush(factory)

    assert ran == 2
    second_handler.assert_awaited_once()


async def test_flush_stops_at_the_round_bound_and_logs_when_work_remains():
    """A handler that keeps republishing must not make flush() loop forever."""
    dispatcher = EventDispatcher()

    async def republish(session, **_):
        await dispatcher.publish("loop.event", session=session)

    dispatcher.subscribe("loop.event", republish)
    factory = FakeSessionFactory()
    await dispatcher.publish("loop.event")

    with patch("app.core.events.logger") as logger:
        ran = await dispatcher.flush(factory)

    assert ran == events_module._MAX_FLUSH_ROUNDS
    logger.error.assert_called_once_with(
        "event_flush_round_limit_reached", rounds=events_module._MAX_FLUSH_ROUNDS, remaining_count=1
    )
