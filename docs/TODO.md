# TODO

Cross-cutting work that no single doc or issue owns. Each item says what it unblocks and
where the reasoning lives, so it can be picked up cold.

**Nothing here is broken.** Most items are a decision deferred to the change that should
make it, in code that is correct as it stands; the rest is hardening that ships no
feature. Behaviour that is wrong today lives in [`BUGS.md`](./BUGS.md). An item leaves
this file when it is done or decided.

---

## Erasure — decide the target state

The erasure cascade runs and is tested, but what it leaves behind is pseudonymised, not
anonymised: `user.id` survives, `conversation.user_id` still points at it, and Langfuse
still holds the conversations keyed by that id.
[`server/docs/gdpr-erasure-findings.md`](../server/docs/gdpr-erasure-findings.md) has
nine open findings (A1–A6, B1–B3, C2), four design options and seven open questions.

**Unblocks:** a truthful privacy policy, and any fork that goes to production with real
supplier contacts. **Decide first:** C2 — one erasure flow for both user types, or two.
It determines whether the rest is one path or two.

Three findings do not wait on that decision and are small on their own:

- **A2 — Langfuse.** Stop sending `langfuse_user_id`, mask content at source, or add a
  deletion call to the cascade. The highest-impact finding.
- **A4 — mem0 failure is silent.** `delete_user_memory` swallows its exception, so a
  failed deletion reports success. Make it propagate, as checkpoint deletion does.
- **A6 — 32-bit `anonymous_id`.** Use the full UUID in `anonymize_user()`.

## Tenancy — `supplier` adopts `TenantMixin`

`supplier` is on the tenancy allowlist because nothing writes the table yet, and adopting
the mixin needs a backfill of `org_id` on existing rows. **Unblocks:** the first supplier
write route, which must ship with the mixin, the backfill migration, and `org_id` on
every `supplier` repository method. Reasoning: `docs/architecture/server.md` §9.

## Data model — native `uuid` primary keys

Every primary key is a `VARCHAR` holding `str(uuid.uuid4())`, generated app-side, with no
server default. A native `uuid` column halves the key and its indexes and rejects
malformed ids; UUID v7 would also make them time-ordered. **Unblocks:** nothing today;
decide before a fork's tables grow large, because the change is a migration of every key
and every foreign key. A `uuidv7()` server default needs **PostgreSQL 18**; the stack runs
16. Conventions: [`data-model/README.md`](./data-model/README.md) §3.

## Authorization — the first organization-scoped route

No route calls `require_role` today: every route is owner-scoped or about the caller
themselves, so no role check has been needed. The first route whose data belongs to an
organization rather than one user needs `CurrentOrgId` into a tenant-scoped repository
**and** a role guard. **Unblocks:** projects, orders and documents — the example domain's
actual screens. Reasoning: [`architecture/authorization.md`](./architecture/authorization.md) §3.

## Authorization — strict role prefix on the server

`AuthMiddleware` parses the role with `removeprefix("org:")`, so an unprefixed value
still parses; the web app's `getUserRole()` rejects one. Clerk always sends the prefix, so
the two agree on every real token. **Unblocks:** nothing today; make it strict before a
second identity provider or a hand-minted token (a test fixture, a service account) can
reach the API. Reasoning: [`architecture/authorization.md`](./architecture/authorization.md) §2.

## Clerk — invitation-only sign-up

The supplier portal has no sign-up page and suppliers are meant to arrive by invitation, but
[`setup/clerk.md`](./setup/clerk.md) has no step restricting sign-ups, so anyone can
sign up through the internal portal and land on `/unauthorized` with no organization. The
supplier portal's `.env.example` also sets `NEXT_PUBLIC_CLERK_SIGN_UP_URL=/sign-up`, a
page it does not have. Open sign-up also stores the stranger: the `user.created` webhook
inserts a user row with their email and names, safe only on an invitation-only instance.
**Unblocks:** a production Clerk instance. Decide whether the internal portal keeps self
sign-up at all; keeping it means gating `user.created` on membership.

## Deploy — per-portal build args

Both portal images are built with the same `NEXT_PUBLIC_API_URL` and
`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`, because the compose file gives both services the
same variable names. Harmless while the portals share one Clerk instance and one API
origin. **Unblocks:** a portal on its own Clerk instance or API origin. The shape:
per-portal variable names in `docker-compose.prod.yml`, and a `deploy-check` assertion on
what each image baked. Reasoning: [`setup/deploy-dokploy.md`](./setup/deploy-dokploy.md).

## Server — the R9 import-linter contract

The rule that a `domain` slot imports no ORM and no framework has no contract yet,
because no module has a `domain` slot. **Unblocks:** nothing until then; it lands with the
first one, as one `forbidden` contract: `app.modules.*.domain` may not import `sqlmodel`,
`sqlalchemy` or `fastapi`. Reasoning: `docs/architecture/server.md` §3.

## Server — events beyond the request

Every entry point is a request, deferred handlers run in-process, and a deferred handler
that fails is logged and lost. **Unblocks:** background jobs and reactions whose loss is
unacceptable. The shape, decided so a fork does not re-decide it:

- **The first job that must not run in a request** — `app/workers/main.py` in the Assembly
  layer, the mirror of `api/v1/api.py`: it imports every module's root, which registers
  the handlers, and drains with `events.flush(session_factory)`. A module's queue consumers are a
  delivery mechanism like its router, and live in the module.
- **The first subscriber that must run on a worker** — the same `publish()` calls; a
  deferred subscription whose handler enqueues to a queue (SQS or similar). Deferred
  already means after-commit, so the publisher's semantics do not change.
- **The first handler whose loss is unacceptable** (billing, an external notification) —
  an `outbox` table written in the publisher's transaction and drained by the worker,
  replacing the in-memory queue for those events.

Reasoning: `docs/architecture/server.md` §8.

## Server — the chat stream ignores a client disconnect

`event_generator()` in `app/modules/conversation/router/chatbot.py` never checks whether
the client is still connected, so a client that leaves mid-stream keeps the LLM call
running to completion. The fix is decided: add `sse-starlette` and return
`EventSourceResponse(event_generator())` in place of the `StreamingResponse`, adapting the
`data: {json}\n\n` framing to its event convention. Rewriting the `BaseHTTPMiddleware`
stack as pure ASGI is not the fix — the gap is in the generator, whatever the middleware.
**Unblocks:** the assistant in production. **Done when** a mid-stream disconnect stops the
LLM call promptly, and the event shape and the middleware behaviour on the route are
unchanged.

## Server — row-level security

Tenancy is enforced in the query layer: every tenant-owned repository method filters by
`org_id`. A forgotten filter is a cross-tenant read, caught today only by review and by
`test_tenant_tables.py` checking that the column exists — not that it is used. Postgres
RLS keyed on a per-transaction `org_id` would make the database refuse the read instead.
**Blocked by** the superuser role in [`BUGS.md`](./BUGS.md): a role with `BYPASSRLS`
ignores every policy. **Unblocks:** defence in depth for the first tenant-owned table.

## Web — tests the suite does not have yet

- **`QueryProvider`'s error policy.** Which queries toast (never-resolved only, unless
  `silentError`), that mutations always do, and that a 4xx is not retried. The mutator and
  the status-recovery hook are covered; the provider that applies their errors is not.
- **End to end.** Nothing drives a browser. The `.spec.` suffix and the `e2e/**` exclude
  are reserved for Playwright; the first flow worth it is sign-in through to a real
  screen, per portal.

Reasoning: [`architecture/web-app.md`](./architecture/web-app.md) §7.
