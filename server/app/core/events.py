"""In-process domain events — the downward-pointing seam between modules.

Modules form a DAG (docs/architecture/server.md, R6): `conversation`
and `supplier` import `account`, so `account` cannot import them. When the
lower module needs a higher one to act — erasing an account must clean up
its conversations — it publishes here and the higher module subscribes.

Two dispatch modes, chosen per subscription:

* inline   — runs in `publish()`, in registration order, in the publisher's
             session and transaction. A handler that raises stops the sequence
             and propagates: the publisher is mid-transaction and must not
             commit a half-done cascade. For cascades.
* deferred — the default. Queued in the request context and run by `flush()`
             after the publisher's commit and before the response is sent,
             each in a session of its own, so they add to response latency.
             A failure is logged and counted, never raised: the write is
             durable and must not be reported as failed. For reactions, and
             the shape a queue will take.

Registration order is import order, which is an isort artifact — subscribers
to one event must not depend on running before or after each other.

A module subscribes at import time (`@events.on(NAME)`), so importing the
module is what registers it; `app/main.py` imports every module by name.
"""

from collections import defaultdict
from contextvars import ContextVar
from typing import (
    Any,
    Awaitable,
    Callable,
    NamedTuple,
)

from app.core.logging import logger
from app.core.metrics import app_event_handler_failures_total

Handler = Callable[..., Awaitable[None]]


class _Subscription(NamedTuple):
    handler: Handler
    inline: bool


class _Queued(NamedTuple):
    event: str
    handler: Handler
    payload: dict[str, Any]


# One queue per request context. The default is None, not a list: a mutable
# default would be shared by every context. `begin()` installs the list at the
# start of a request so that code running in a worker thread — which gets a
# *copy* of the context — appends to the same object the request will flush.
_queue: ContextVar[list[_Queued] | None] = ContextVar("app_events_queue", default=None)

# Bounds a chain of deferred handlers where one publishes another deferred
# event: flush() re-drains after its loop (see flush()), and this caps the
# re-drains so a handler that keeps republishing cannot make flush() loop
# forever.
_MAX_FLUSH_ROUNDS = 5


def _qualified_name(handler: Handler) -> str:
    return f"{handler.__module__}.{getattr(handler, '__qualname__', repr(handler))}"


class EventDispatcher:
    """Registry of async handlers keyed by event name.

    Only one instance is supported per process: `_queue` above is a
    module-global `ContextVar`, shared by every instance rather than scoped
    to one, so `begin()` on one instance clears every other instance's
    queue. `events` below is the one supported instance.
    """

    def __init__(self) -> None:
        """Start with no subscriptions."""
        self._subscriptions: dict[str, list[_Subscription]] = defaultdict(list)

    def subscribe(self, event: str, handler: Handler, *, inline: bool = False) -> Handler:
        """Register `handler` for `event`. Returns the handler unchanged."""
        self._subscriptions[event].append(_Subscription(handler, inline))
        return handler

    def on(self, event: str, *, inline: bool = False) -> Callable[[Handler], Handler]:
        """Decorator form of subscribe()."""

        def decorator(handler: Handler) -> Handler:
            return self.subscribe(event, handler, inline=inline)

        return decorator

    def handlers(self, event: str) -> tuple[Handler, ...]:
        """The handlers registered for `event`, in registration order."""
        return tuple(s.handler for s in self._subscriptions.get(event, ()))

    def subscriptions(self, event: str) -> tuple[_Subscription, ...]:
        """The subscription records for `event`, in registration order.

        Unlike `handlers()`, each record keeps its dispatch mode (`inline`),
        so a test can assert a subscription's mode and not just its presence.
        """
        return tuple(self._subscriptions.get(event, ()))

    def begin(self) -> None:
        """Start an empty deferred queue for the current context."""
        _queue.set([])

    async def publish(self, event: str, **payload: Any) -> int:
        """Run the inline handlers now and queue the deferred ones.

        Inline handlers receive `payload` as keyword arguments, `session`
        included. Deferred handlers are queued with the payload minus
        `session`; `flush()` gives each one a session of its own.

        Returns the number of handlers run plus queued.
        """
        subscriptions = self._subscriptions.get(event, [])
        deferred_payload = {k: v for k, v in payload.items() if k != "session"}
        for subscription in subscriptions:
            if subscription.inline:
                await subscription.handler(**payload)
                continue
            queued = _queue.get()
            if queued is None:
                queued = []
                _queue.set(queued)
            queued.append(_Queued(event, subscription.handler, deferred_payload))
        logger.debug("event_published", event_name=event, handler_count=len(subscriptions))
        return len(subscriptions)

    async def flush(self, session_factory: Callable[[], Any]) -> int:
        """Run every queued deferred handler, each in a fresh session.

        A handler that raises is logged as `event_handler_failed`, counted on
        `app_event_handler_failures_total`, and skipped; the rest still run.
        A handler that itself publishes a deferred event queues more work,
        so the queue is re-drained after each round, up to `_MAX_FLUSH_ROUNDS`;
        if work is still queued after that many rounds, it is left queued and
        logged as `event_flush_round_limit_reached` rather than looped on
        forever. Returns the number of handlers attempted, not counting any
        left queued at the bound.

        Callers outside a request — a script, a worker — call this themselves.
        """
        total_ran = 0
        for _round in range(_MAX_FLUSH_ROUNDS):
            queued = _queue.get()
            if not queued:
                return total_ran
            _queue.set(None)
            for entry in queued:
                try:
                    async with session_factory() as session:
                        await entry.handler(session=session, **entry.payload)
                        await session.commit()
                except Exception:
                    handler_name = _qualified_name(entry.handler)
                    logger.exception("event_handler_failed", event_name=entry.event, handler=handler_name)
                    app_event_handler_failures_total.labels(event=entry.event, handler=handler_name).inc()
            total_ran += len(queued)

        remaining = _queue.get()
        if remaining:
            logger.error("event_flush_round_limit_reached", rounds=_MAX_FLUSH_ROUNDS, remaining_count=len(remaining))
        return total_ran


events = EventDispatcher()
