# Inbound Webhooks (Provider → Us)

The other half of `references/client-wrappers.md`. That file covers the calls we make to a provider; this one covers
the events they push to us. The protocol lives in the same `app/integrations/<provider>/` package — see that file
for why — and the handlers live in the module that owns the table they write:

```
app/integrations/clerk/webhooks/       # the protocol
├── verification.py                    # signature check -> VerifiedEvent
├── schemas.py                         # the envelope, and what handlers receive
└── exceptions.py                      # ingestion errors (401/413), separate from the client's

app/modules/account/webhooks.py        # the meaning: event type -> handler registry, and the handlers
app/modules/account/router/webhooks.py # the receiver route
```

Four stages, in order: **verify → parse → dispatch → handle**. Each stage's output is the next one's only input, so
the flow reads top to bottom — verification in the integration, then dispatch and handlers together in one module
file — and every stage is testable alone.

## Verification

A webhook endpoint has **no JWT and no session** — the signature is the only credential. Auth middleware must let
these requests through without setting an identity, and the route must be unauthenticated by design.

Verify in a **FastAPI dependency that returns a typed value**, not a bool and not a bare parse:

```python
async def verify_clerk_webhook(request: Request) -> VerifiedEvent:
    body = await _read_body_capped(request)
    headers = dict(request.headers)          # Starlette lower-cases header names

    try:
        # The raw bytes are the signed artifact. Parsing and re-serialising would change
        # key order or whitespace and break the HMAC, so decode the same object the
        # signature just accepted.
        Webhook(secret).verify(body, headers)
        event = ClerkEvent.model_validate(json.loads(body))
    except (SvixWebhookVerificationError, ValueError) as exc:
        logger.warning("webhook_verification_failed", reason=type(exc).__name__)
        raise InvalidWebhookSignatureError("Invalid webhook signature") from exc

    return VerifiedEvent(event=event, message_id=headers.get("svix-id", ""))
```

Three things that are easy to get wrong:

**One error for every failure mode.** Forged signature, missing header, stale timestamp, malformed secret,
unparseable body — all raise the same exception with the same message. The response is rendered to the caller, so
distinguishing them hands an attacker an oracle telling them which check they failed. Log the discriminator
(`reason=type(exc).__name__`), return one message.

**Cap the body while reading it, not after.** `await request.body()` buffers everything and only then lets you
measure it — that bounds what you hash, not what you allocate. Consume `request.stream()` and bail at the first
chunk crossing the cap, so peak allocation is the cap plus one in-flight chunk. A `Content-Length` pre-check is not
enough on its own: chunked transfer-encoding just omits the header. This endpoint is unauthenticated and
unthrottled, so the cap has to be enforced here.

**Capture the delivery id.** The provider's delivery id (`svix-id` for Clerk/svix) is what lets a log line be matched
against a delivery in the provider's dashboard, and it is the key any future dedup table would use. It costs one
line at the point where you already hold the headers, and is very annoying to retrofit — the whole pipeline's
signatures change.

## What handlers receive

Two frozen dataclasses in `schemas.py`, so `verification.py` and the account module's `webhooks.py` never import
each other — the route composes them:

```python
@dataclass(frozen=True, slots=True)
class VerifiedEvent:                # what verification returns
    event: ClerkEvent
    message_id: str

@dataclass(frozen=True, slots=True)
class WebhookContext:               # what handlers receive
    event: ClerkEvent
    message_id: str
    session: AsyncSession

    @property
    def data(self) -> dict[str, Any]:
        return self.event.data
```

**The context carries per-delivery facts only.** Never put a process-wide capability in it — an agent, a service
singleton, a client. Those aren't properties of this delivery; a handler that needs one imports it, the way every
other module reaches a singleton. Threading one through the context makes every handler's signature advertise a
dependency it doesn't have, and the parameter then gets couriered through call sites that only pass it along.

Pass the **envelope**, not just `data`. A handler given a bare payload can never see the event type or the delivery
id, and adding either later means touching every signature.

Model the payload body as a plain `dict`, not a per-event Pydantic model. Providers add fields without notice, and a
strict model rejects deliveries over additions you don't read.

## Dispatch

A registry keyed by event type, not a chain of conditionals — each handler stays independently testable, and the
registration block doubles as the readable list of events this app subscribes to.

```python
WebhookHandler = Callable[[WebhookContext], Awaitable[None]]

async def dispatch(self, ctx: WebhookContext) -> None:
    handler = self._handlers.get(ctx.event.type)
    if handler is None:
        logger.info("webhook_event_unhandled", event_type=ctx.event.type, message_id=ctx.message_id)
        return
    await handler(ctx)
    logger.info("webhook_event_processed", event_type=ctx.event.type, message_id=ctx.message_id)
```

**An unhandled event type must not raise.** You are subscribed to a superset of what you handle, and providers
disable endpoints that keep failing — so raising on an event you don't care about eventually costs you the events
you do.

**Register every spelling the provider might send.** Clerk's dashboard catalog names membership events in camelCase
while its log docs use snake_case; the wrong key fails *silently* — the handler never runs, no error, no 4xx. When
the provider's own docs disagree, register both.

## Handlers

Handlers are the anti-corruption layer: they translate one provider event into domain calls and own no logic of
their own. They live in the module that owns the rows they write (`app/modules/account/webhooks.py`), beside the
dispatcher; the provider package under `app/integrations/` only verifies and parses, and imports nothing from
`app/modules/`. When an event needs a higher module to act, the handler publishes rather than imports it — the
`user.created` and `organization_membership.created` handlers publish `USER_SYNCED`, the `.deleted` membership one
`USER_OFFBOARDED`, and `supplier` subscribes (`references/services.md`,
**Event subscribers**).

**Every handler must be idempotent.** Delivery is at-least-once. Without a dedup table, a replay inside the
signature's tolerance window has to converge rather than duplicate — so a create handler applies its payload as an
update when the row already exists.

**Order with the provider's clock, never the host's.** Providers guarantee no ordering, so two updates can arrive
reversed. Compare the payload's timestamp against a `last_synced_at` column and drop the stale one. The trap is the
fallback: if an absent timestamp makes you write `now()` into that column, a fast local clock makes every future
legitimate event look stale forever. Seed rows with an explicit epoch constant instead, so an unsynced row is older
than any real event:

```python
UNSYNCED_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
...
last_synced_at=event_ts or UNSYNCED_EPOCH,     # never `or datetime.now(UTC)`
```

Compare strictly (`event_ts < user.last_synced_at`): an identical timestamp should be applied, because the write is
idempotent and a same-millisecond distinct event is the worse thing to lose.

**Never resurrect deleted rows.** An `*.updated` handler must not create. If erasure anonymises by rewriting the
provider's id, a deleted user is indistinguishable from one who never existed — so creating on an unknown id
resurrects people who exercised their right to erasure. Log and decline. A create handler (`user.created`, a
membership) inserts only after asking the provider whether the user still exists — a redelivered pre-erasure
snapshot would otherwise re-insert the erased PII (`user_service.exists_in_clerk`: a 404 declines, any other error
propagates).

**Raise to earn a redelivery.** Swallowing an exception returns 2xx and the provider considers the delivery done. A
step that must not be silently skipped has to propagate — that is the only retry mechanism the path has.

## The route

The endpoint lives in the owning module's router (`app/modules/account/router/webhooks.py`) — only the protocol
machinery lives in `integrations/`. It composes the context
and does nothing else:

```python
async def clerk_webhook(
    verified: Annotated[VerifiedEvent, Depends(verify_clerk_webhook)],
    session: DbSession,
) -> None:
    await clerk_dispatcher.dispatch(
        WebhookContext(event=verified.event, message_id=verified.message_id, session=session)
    )
```

Return `204` and no body, and `include_in_schema=False` so it stays out of the generated client. **Carry no rate
limit**: providers burst on retry, and a `429` reads as a failed delivery and provokes further retries. The signature
check is the gate and it is cheap. (Today every undecorated route is unlimited, since there is no
`SlowAPIMiddleware`; this is a rule for when that changes, not a description of the present.)

## Rules

- Signature verification is the only credential — dependency in, typed value out, never a bool
- One indistinguishable error for every verification failure; log the reason, don't return it
- Cap the body while streaming it; `Content-Length` alone is not a cap
- Capture the delivery id at verification and carry it to the dispatch log
- `WebhookContext` holds per-delivery facts only — no singletons, no agents, no clients
- Pass the envelope, not the payload; keep the payload a `dict`
- Registry over conditionals; unhandled types log and return
- Handlers are idempotent, order on the provider's clock, and never create on `*.updated`
- Never log payload PII (emails, names) or leak DB constraint text into a response body
- Webhook ingestion gets its own `exceptions.py`, separate from the outbound client's

## Testing

- **Unit** — verification with real signed bodies plus the failure modes (bad signature, missing header, stale
  timestamp, oversized body) in `tests/unit/integrations/<provider>/`; handlers and the dispatch registry, with a
  mocked session and a local `ctx()` helper, in `tests/unit/modules/<name>/`
- **Integration** (`tests/integration/modules/<name>/router/`) — the route end to end against a real DB, posting
  genuinely signed bodies. This is the only layer that proves verification, the registry and the DB write agree
- Assert **step order** where a cascade's order is contractual, not just that each step ran
