# WS4 — Clerk Webhooks

**Date:** 2026-08-26
**Status:** Approved, not implemented
**Supersedes:** the WS4 section of `2026-08-24-template-hardening-design.md`

---

## Problem

User records reach the database only through JIT provisioning in
`UserService.resolve_user`. Nothing in Clerk pushes to us, so a profile edit,
a role change, an org removal, or a deletion performed in the Clerk dashboard
never reaches the database. Role revocation is bounded only by the 60-second
`UserCache` role TTL, and a dashboard-initiated deletion leaves the user row,
their LangGraph checkpoints, and their mem0 memories untouched.

---

## Decisions

**D-1. Webhooks are the source of truth for user state; JIT is retained as the
ordering backstop.** This is stronger than "fallback". JIT's specific job in
this design is to repair state that out-of-order membership events can leave
wrong — `resolve_user` re-syncs `org_id` from the JWT on the next request.
Removing JIT would turn a rare inconsistency into a permanent one.

**D-2. Six events are handled:** `user.created`, `user.updated`,
`user.deleted`, and the three organization membership events (see the casing
note below).

**Event name casing — verify empirically before trusting either source.**
The Clerk dashboard's webhook catalog lists these in camelCase
(`organizationMembership.created`); `docs/guides/dashboard/logs/application-logs.mdx`
lists them in snake_case. Those are two different taxonomies — application
logs are not webhook message types — and the dashboard is what Svix
registers. The original hardening spec and the TODO at
`app/services/user/service.py:171` used camelCase and were most likely right.

A wrong key fails silently: the handler never runs, with no error and no
4xx. The registry therefore holds **both** spellings, and the endpoint's
Testing tab settles which one actually arrives.

`user.created` is included even though JIT already covers creation: it is
Clerk's canonical sync recipe, and it gives a correct `created_at` and a row
for an invited user who never logs in. It is safe to handle unconditionally
because the Clerk instance is invitation-only — every `user.created`
corresponds to someone a project manager already authorised. **If public
sign-up is ever enabled, this handler becomes an unauthenticated row-creation
vector and must be gated on org membership.**

**D-3. No dedup table.** svix verification supplies signature validity and a
five-minute timestamp tolerance. Within that window a replay is possible, but
every handler here is naturally idempotent — `user.updated` applies a snapshot,
`user.deleted` anonymises an already-anonymised row, membership handlers set an
`org_id` that is already set. A dedup table would buy exactly-once semantics
for operations that are already safe to repeat.

**Trigger to revisit:** the first non-idempotent side effect (a welcome email,
a billing call, anything that emits rather than converges). At that point add
a `webhook_event` table with a unique constraint on the `svix-id` header,
insert-first.

**D-4. `user.deleted` runs the full erasure cascade, not just anonymisation.**
The hardening spec said "trigger `anonymize_user` rather than a hard delete".
Read literally that leaves chat transcripts in LangGraph checkpoints and
extracted facts in mem0, with no user row left pointing at them, so nothing
would ever clean them up. A dashboard deletion must be as GDPR-complete as a
self-service one.

**D-5. Removal from an org unlinks the supplier.** `organization_membership.deleted`
clears `User.org_id`, invalidates the caches, and clears `Supplier.contact_id`,
mirroring the GDPR path. Accepted cost: the supplier silently becomes
contact-less with no signal to a project manager. Mitigated only by a
`supplier_unlinked_on_offboarding` log event. See Follow-ups.

**D-6. The secret is enforced by `REQUIRED_ENV_VARS`, not by a required
pydantic field.** `AuthSettings.WEBHOOK_SIGNING_SECRET` keeps
`Field(default=SecretStr(""))`, matching its neighbours, and the dependency
performs no runtime presence check.

A required pydantic field would validate at import in every process importing
`app.core.config` — including `alembic/env.py:28`. The `migrate` one-shot
service would then have to carry a webhook secret it never uses, defeating the
deliberate `REQUIRED_ENV_VARS=` opt-out documented in
`scripts/docker-entrypoint.sh:57`, and since `server` is gated on `migrate` via
`service_completed_successfully`, a missing secret would present as a failed
migration.

Accepted gap: the entrypoint guards containerised runs only. A host-side
`make dev` without the secret still boots, and every webhook request 401s
because an empty HMAC key never matches. Fail-closed, but less legible.

**D-7. ngrok, not cloudflared.** Unchanged from the hardening spec. Every ngrok
account including the free tier gets one permanent static domain, so the Clerk
dashboard endpoint URL is set once and survives restarts.

---

## Architecture

```
POST /api/v1/webhooks/clerk
  │
  ├─ verify_clerk_webhook  (app/api/dependencies/webhook.py)
  │    raw body → size cap → svix verify → ClerkEvent
  │
  └─ ClerkWebhookService.dispatch  (app/services/clerk/webhooks/service.py)
       event type → handler → repositories / user_service
```

**New files**

| Path | Purpose |
|---|---|
| `app/api/dependencies/webhook.py` | Signature verification dependency |
| `app/schemas/webhook.py` | `ClerkEvent` and per-event payload models |
| `app/services/clerk/webhooks/service.py` | Handler registry and the six handlers |
| `app/services/clerk/webhooks/exceptions.py` | Domain exceptions extending `ServiceError` |
| `app/api/v1/webhooks.py` | Route |

**Modified**

| Path | Change |
|---|---|
| `pyproject.toml` | add `svix` |
| `app/core/config.py` | `AuthSettings.WEBHOOK_SIGNING_SECRET` |
| `app/api/v1/api.py` | include the webhooks router |
| `app/api/v1/auth.py` | `delete_me` calls the extracted `erase_user()` |
| `app/services/user/service.py` | extract `erase_user()` and `link_supplier_from_metadata()`; write `last_synced_at` from Clerk's clock; drop the stale TODO at line 171 |
| `scripts/docker-entrypoint.sh` | add `CLERK_WEBHOOK_SIGNING_SECRET` to the default `REQUIRED_ENV_VARS` |
| `docker-compose.dev.yml` | `ngrok` service |
| `.env.example`, `.env.development`, `.env.test` | `CLERK_WEBHOOK_SIGNING_SECRET` |

---

## Verification dependency

```python
async def verify_clerk_webhook(request: Request) -> ClerkEvent:
    body = await request.body()
    if len(body) > MAX_WEBHOOK_BODY_BYTES:          # 256 KiB
        raise WebhookPayloadTooLargeError(...)      # 413

    try:
        payload = Webhook(
            settings.auth.WEBHOOK_SIGNING_SECRET.get_secret_value()
        ).verify(body, dict(request.headers))
    except SvixWebhookVerificationError as e:
        raise InvalidWebhookSignatureError("Invalid webhook signature") from e

    return ClerkEvent.model_validate(payload)
```

Constraints, each load-bearing:

- **Verify the raw bytes.** `await request.body()` and nothing else. Parsing
  and re-serialising changes key order or whitespace and breaks the HMAC.
- **Size cap precedes the HMAC.** Starlette buffers the body in memory; without
  a cap an unauthenticated caller makes us allocate and hash arbitrary input.
  Clerk payloads are a few KB.
- **One error for every verification failure.** svix raises the same exception
  for a bad signature, a missing `svix-id`, and a timestamp outside tolerance.
  All become 401. No branch reveals which check failed.
- **No `to_thread`.** The HMAC is microseconds of CPU.
- **No rate limit on the route.** svix bursts on retry; a 429 reads as failure
  and provokes more retries. The signature is the gate.
- **No auth exemption needed.** `AuthMiddleware` is already permissive.

Exceptions extend `ServiceError` so `service_exception_handler` maps them —
no try/except in the route, per `server/CLAUDE.md`.

### One thing to verify during implementation

`get_db_session` calls `set_session_context(session, request.state.user_id)`,
and on the webhook path that value is `None` (`AuthMiddleware` initialises it
so). This is inert today — `set_config` is strict, so a NULL is a no-op, and
the same already happens on every unauthenticated request. But it means the
webhook's session carries no `app.current_user_id`. If RLS policies are ever
enforced on the `user` table, this path is blocked and needs an explicit
system-context escape hatch. Leave a comment in the handler rather than
rediscovering it later.

---

## Ordering

Clerk guarantees neither ordering nor exactly-once delivery. Two distinct
failure modes, two distinct fixes.

### Monotonic guard on profile events

```python
event_ts = datetime.fromtimestamp(payload["updated_at"] / 1000, tz=UTC)
if event_ts < user.last_synced_at:
    logger.info("webhook_event_stale", clerk_id=..., event_ts=..., synced_at=...)
    return                      # 200, deliberately
user.last_synced_at = event_ts  # Clerk's clock, never ours
```

**`last_synced_at` must hold Clerk's timestamp, not ours.** Comparing our wall
clock against Clerk's makes host clock skew silently corrupt every decision —
skew in one direction drops legitimate updates indefinitely. Both writers must
share one clock, and Clerk's is the only one both see.

**This obliges a JIT change.** Today `last_synced_at` receives
`datetime.now(UTC)` from the field default at creation and is never written
again (`app/models/user.py:52`). `resolve_user` must set it from
`clerk_user.updated_at`. This is the least obvious ripple in the workstream.

Compare with strict `<` so a same-millisecond duplicate still applies; it is
idempotent, and that is cheaper than risking a dropped distinct event.

`user.deleted` needs no guard. Its payload is a `DeletedObjectJSON` with no
`updated_at`, and it is self-protecting: after erasure `clerk_id` is rewritten
to `deleted_user_<prefix>`, so any later event for the original id finds no row.

### Missing-antecedent policy

| Event | Row missing | Rationale |
|---|---|---|
| `organization_membership.*` | **Create from `public_user_data`**, once Clerk confirms the user exists | The payload carries `user_id`, `identifier` (email), `first_name`, `last_name`, `image_url`, plus `role` and `organization`, so the row is built from the payload rather than a second fetch. One `GET /users/{id}` gates the insert — see the amendment below. |
| `user.updated` | No-op, log a warning | Never creates. See the invariant. |
| `user.deleted` | No-op | Already erased. |
| `user.created` | *(row present)* apply as an update through the guard | Makes create/update reversal harmless. |

### Invariant: never resurrect a deleted user

`user.updated` for an unknown `clerk_id` has two indistinguishable causes — the
create event has not landed yet, or the user was erased. `anonymize_user()`
rewrites `clerk_id`, so an erased user looks exactly like one who never
existed. The handler is therefore update-only, choosing the GDPR-safe side of
an ambiguity that cannot be resolved.

**Accepted cost:** a `user.created`/`user.updated` pair reversed within
milliseconds loses the update until Clerk sends the next one. JIT does *not*
heal this — `resolve_user` refreshes `org_id` only, not names or email.

**Amended 2026-08-27 (post-review):** the invariant as written covered only
`user.updated`, leaving the two *create* paths — `handle_user_created` and the
membership handler's `_resolve_or_create_user` — free to insert from a payload
alone. svix redelivers with backoff, so a delivery whose snapshot predates a
deletion can land after it, and the erased email and names go back into the
database. Both paths now resolve the ambiguity instead of choosing a side:
`UserService.exists_in_clerk` asks Clerk, which is the only party that can
still tell "erased" from "create has not landed yet" once `clerk_id` has been
rewritten. Only a 404 declines; every other Clerk error propagates, so an
inconclusive answer earns a redelivery rather than a row. The lookup sits
below the local guards, so it costs roughly one call per genuinely new user
and none at all when the row already exists.

### No membership sync column

Reusing `last_synced_at` for membership events would conflate two unrelated
clocks: a fresh `user.updated` would begin dropping older-but-valid membership
events. A dedicated column is machinery for a rare case. Instead, per D-1, JIT
is the backstop — a reversed membership pair leaving a user org-less is
repaired from the JWT on their next request (`app/services/user/service.py:64`).

---

## Handlers

| Event | Behaviour |
|---|---|
| `user.created` | Upsert. Existing row → apply as update through the guard. Inserts with `org_id=None` (the payload has no org — Clerk models membership separately) and `last_synced_at` from `data.updated_at`. Links a supplier if `public_metadata.supplier_id` is present. |
| `user.updated` | Update-only through the guard. Never creates. |
| `user.deleted` | `user_service.erase_user()`. No-op if the row is gone. |
| `organization_membership.created` | Upserts the user from `public_user_data` if missing, sets `org_id`, invalidates the role cache, links a supplier from the membership's `public_metadata`. |
| `organization_membership.updated` | Sets `org_id`, invalidates the role cache. |
| `organization_membership.deleted` | Clears `org_id`, clears `Supplier.contact_id`, invalidates both caches, logs `supplier_unlinked_on_offboarding`. |

Unknown event types log and return 204. Never an error status — Clerk retries
those and eventually disables the endpoint.

### Invalidate the cache; never populate it

`UserCache`'s own contract (`app/services/user/cache.py:146`) states that
dropping an entry before commit can only cost a DB read, whereas populating
before commit can serve a value for a transaction that later rolls back.
Handlers run inside `get_db_session`, which commits only after the route
returns. Every handler therefore invalidates and none call `set_org_role` —
including `organization_membership.updated`, even though the event hands us the
new role. The next request repopulates from Clerk.

### Extracted from existing code

**`user_service.erase_user(user, session, agent)`** — steps 2–7 of `delete_me`
(`app/api/v1/auth.py:80`). The route becomes `delete_user_from_clerk()` then
`erase_user()`; the webhook calls `erase_user()` alone, since the Clerk-side
deletion is what produced the event. This also makes the self-delete echo
harmless: `DELETE /me` triggers `user.deleted` back at us, and the handler
finds an anonymised row and no-ops.

**`user_service.link_supplier_from_metadata(user, metadata, session)`** — the
block currently inline in `resolve_user` (`app/services/user/service.py:104-155`)
reading `public_metadata.supplier_id` and the `replace` flag. Three call sites
now need it. It is already idempotent — linking only when `contact_id is None`
or `replace` is set — which is exactly what a retried webhook requires.

---

## Dev infrastructure

`docker-compose.dev.yml` only:

```yaml
ngrok:
  image: ngrok/ngrok:latest
  command: http server:8000 --url=${NGROK_DOMAIN}
  environment:
    NGROK_AUTHTOKEN: ${NGROK_AUTHTOKEN}
  depends_on: [server]
  networks: [app-network]
```

`NGROK_AUTHTOKEN` and `NGROK_DOMAIN` live in the root `.env` beside
`GRAFANA_ADMIN_PASSWORD`. The static domain is the point: the Clerk dashboard
endpoint URL is configured once. No new `Makefile` target — `make docker-run`
brings it up. Not present in `docker-compose.prod.yml`.

**Caveat to document in the README:** dev and production are separate Clerk
instances with different signing secrets. A dev secret in a production env
file 401s every real event.

---

## Testing

**Unit — dependency** (`tests/unit/api/test_webhook_dependency.py`). This is
the entire security boundary, so it is tested adversarially: valid signature
passes; tampered body rejected; body re-serialised with reordered keys rejected
(proves raw-byte verification); timestamp outside the five-minute tolerance
rejected; each of `svix-id` / `svix-timestamp` / `svix-signature` missing
rejected; signature from a different secret rejected; oversized body rejected
before verification runs. Sign fixtures with `svix.webhooks.Webhook.sign`
rather than hand-rolled HMACs.

**Unit — handlers** (`tests/unit/services/test_clerk_webhooks.py`), mocked
repository. Per event: happy path; **applied twice, identical end state** — the
idempotency claim D-3 rests on; stale `updated_at` dropped; missing row follows
the policy table. Plus both invariants explicitly: `user.updated` never creates
a row, and no handler calls `set_org_role`.

**Integration** (`tests/integration/api/test_webhooks.py`), real DB: a signed
request end-to-end per event; a reversed `organization_membership.created` →
`user.created` pair leaving correct state; `user.deleted` running the full
cascade, and a replay of it no-oping.

The test secret must be a genuine `whsec_<base64>` string — svix base64-decodes
the secret in the `Webhook` constructor, so `whsec_dummy` raises before any
assertion runs.

---

## Out of scope / follow-ups

- **`webhook_event` dedup table.** Trigger: the first non-idempotent side
  effect (D-3).
- **Contact-less supplier signal.** D-5 leaves a supplier with no contact and
  only a log line. A `contact_status` column plus internal-portal surfacing
  belongs to whichever workstream owns the supplier list.
- **`env_file` on nested settings models.** `AuthSettings`, `DatabaseSettings`
  and the others declare no `env_file`, so they read `os.environ` only. This is
  currently absorbed by `set_env.sh` exporting, compose `env_file:` injecting,
  and `tests/conftest.py:24` calling `load_dotenv(".env.test")`. It works, but
  it is three mechanisms compensating for one gap. A sweep is its own change.
- **Non-user Clerk events** — `organization.*`, `session.*`,
  `organization_invitation.*` — are not subscribed.

---

## Risks accepted

| Risk | Mitigation |
|---|---|
| Replay within the five-minute svix tolerance | Handlers are idempotent (D-3) |
| Reversed create/update loses a profile edit | Millisecond window; healed by the next Clerk-side change |
| Erasure cascade exceeds the svix timeout and is retried | The cascade is idempotent; retries converge |
| Host-side `make dev` with no secret 401s opaquely | Fail-closed; documented in D-6 |
| Public sign-up would make `user.created` an open row-creation vector | Instance is invitation-only; flagged in D-2 |
| A retried `organizationMembership.created` lands after its user was erased, inserting a fresh row with `identifier`/`first_name`/`last_name` | None — accepted. `handle_membership_created` *is* permitted to create (unlike `user.updated`), and the "never resurrect" reasoning that gates `user.updated` applies here too: `anonymize_user()` rewrites `clerk_id`, so an erased user is indistinguishable from one who never existed, and there is no key left to match the retry against. No cheap mitigation exists. |
