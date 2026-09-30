# Events

`app/core/events.py` is an in-process dispatcher: a lower module publishes, a higher module subscribes, and the
publisher never imports the subscriber. What it is and the events that exist are in `docs/architecture/server.md`
§8; this file is when to reach for it, how to publish and subscribe, and what it will not do for you.

## When to use it

| The situation | The answer |
|---|---|
| A module needs a module *above* it in the DAG to act (erasing a user must clean up conversations) | Publish an event; the higher module subscribes |
| A module needs a module *below* it to act | Call its service singleton through its root — not an event |
| A module needs data from a module above it (`account`'s `/auth/me` wants the supplier's name) | Not an event: `publish()` returns a count, never data. The route or the data belongs in the higher module (R6) |
| A module needs an adapter (`app/agents/`, `app/integrations/`) to act | Call it directly; adapters are below every module |
| One part of a module needs another part of the same module | A plain function call |
| Work that must survive a crash, retry, or run off the request | Not this dispatcher yet — see **Limits** |

Where the modules sit in the DAG is the R6 contract in `server/pyproject.toml`: a module can publish only to modules
listed above it there.

## Publishing

```python
# app/modules/account/service.py — namespaced by module, re-exported from the root
USER_ERASING = "account.user_erasing"

# app/modules/account/service.py, in erase_user
subscriber_count = await events.publish(USER_ERASING, session=session, user_id=user.id)
logger.info("user_erased", user_id=user.id, subscriber_count=subscriber_count)
```

- The name is a constant on the publisher's root, so a subscriber imports it and a rename is an import error.
- The payload is `session=` plus plain values — ids, strings, dicts. Not model instances: a deferred handler gets
  a different session (see **Pitfalls**).
- Publish from the service or a webhook handler, after the write the event announces, and never from a repository.
- Where a missing subscriber would be a silent failure — erasure — log the returned count.

## Subscribing

```python
# app/modules/conversation/handlers.py
@events.on(USER_ERASING, inline=True)
async def erase_on_user_erasing(session: AsyncSession, user_id: str) -> None:
    await conversation_service.soft_delete_all_user_conversations(session, user_id)
    ...

# app/modules/conversation/__init__.py — last, with the comment
# @events.on is a module-level side effect: importing the root is what subscribes.
from app.modules.conversation import handlers
```

- One module-level function per event, in the `handlers` slot, named `<verb>_on_<event>`.
- The handler takes `session` and the payload's keywords by name. It calls this module's service singleton, not
  its repository, so a test can patch `<name>_service.<method>`.
- A new module must be imported by name in `app/main.py`, or its handlers never register
  (`test_main_imports_every_module_explicitly` catches it).

## Choosing the mode

Ask: **if this handler fails, should the publisher's write be undone?**

- **Yes → `inline=True`.** A cascade that is part of the command's own consistency: erasure is not done while a
  supplier row still points at the anonymised user. The handler runs inside `publish()`, in the publisher's session
  and transaction; an exception propagates and the request rolls back. It never commits. Every subscription today
  is inline.
- **No → deferred (the default).** A reaction to something that already happened: a notification, a cache warm-up,
  a projection. It runs after the commit, before the response is sent, in a fresh session the dispatcher commits.
  An exception is logged as `event_handler_failed`, counted on `app_event_handler_failures_total`, and swallowed —
  the caller still gets its 2xx.

An external call (email, HTTP API) in an inline handler makes the request's success depend on that provider, and
it cannot be rolled back if the transaction later fails. Put it in a deferred handler — and if losing it on a
failure is unacceptable, that is the case **Limits** describes, not a reason to make it inline.

## Pitfalls

- **Model instances in the payload.** `publish()` strips only `session` from a deferred payload. A `User` passed as
  `user=user` reaches the handler still bound to the publisher's session: a lazy attribute raises `MissingGreenlet`
  (or `DetachedInstanceError` once that session is closed), and `session.add(user)` fails. Pass `user_id` and load it
  in the handler's session. Inline handlers share the session, so an instance is safe there — but a plain id is
  safe in both, and a subscription's mode may change later.
- **Handlers must be idempotent.** An event can be published more than once for one fact: `USER_SYNCED` fires on JIT
  provisioning *and* on each `user.created` / `organization_membership.created` webhook, and Clerk redelivers
  webhooks. A handler that sends an email records that it did.
- **No ordering between subscribers.** Handlers for one event run in registration order, which is import order,
  which isort decides. A handler that needs another's result is one handler, or one handler calling a service.
- **Deferred handlers add latency.** They run before the response is sent. A slow reaction slows the request.
- **Outside a request, nothing drains the queue.** Begin and flush live in the `DbSession` dependency. A script
  or worker that publishes does both itself, or its deferred handlers silently never run:

  ```python
  import app.main  # noqa: F401 — registers every module's handlers
  events.begin()   # sync; before any publish, and before fanning out with gather/create_task
  ...              # publish, then commit
  await events.flush(session_factory)  # create_session_factory(engine) from app/database/engine.py
  ```

  Skipping `begin()` breaks fan-out: each task then queues into its own copy of the context, which the caller's
  `flush` cannot see.
- **Chains are bounded.** A deferred handler that publishes another deferred event is drained in the same flush, up
  to five rounds; past that the rest is logged as `event_flush_round_limit_reached` and left queued — in a request, that means lost.
- **One dispatcher.** Use the `events` singleton; a second `EventDispatcher` shares the same queue.

## Limits

- **In-process only.** No persistence, no retry. A deferred handler that fails, or a process that dies between the
  commit and the flush, loses the reaction.
- **Request-scoped.** Every entry point today is an HTTP request.

When a reaction's loss is unacceptable or work must leave the request, the path is already decided — a worker
entry point, then a deferred handler that enqueues, then an outbox table (`docs/TODO.md`, **Server — events beyond
the request**). Do not build a parallel mechanism.

## Testing

- **Unit-test the handler** as a plain async function with a mocked session and the service patched by path.
- **Assert the mode**, not just the subscription: `events.subscriptions(USER_ERASING)` returns records carrying
  `inline`.
- **Assert the publish** in the publisher's test by patching `…service.events.publish`.
- A route test through the `client` fixture never runs deferred handlers — it replaces `get_db_session`, and the
  flush with it. Load the `server-testing` skill.

## Checklist

- [ ] The publisher is below the subscriber in the R6 order; otherwise it is a direct call
- [ ] Event name is a namespaced constant exported from the publisher's root
- [ ] Payload is `session` plus plain values — no model instances
- [ ] Handler is in `handlers.py`, imported last by the root; the module is imported in `app/main.py`
- [ ] Mode chosen by "should a failure undo the write?"; external calls are deferred
- [ ] Handler is idempotent and does not depend on other subscribers' order
- [ ] Tests: the handler, its mode, and the publish
