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
still holds the conversations keyed by that id. Every finance table added by the backend
modules joins the cascade.
[`server/docs/gdpr-erasure-findings.md`](../server/docs/gdpr-erasure-findings.md) has
open findings, four design options and open questions; the findings that concern the
removed example domain are moot.

**Unblocks:** a truthful privacy policy, and going to production with real users.
**Decide first:** what "erased" means for the `user` row and for the tracing service. That
determines whether the rest is one path or several.

Two findings do not wait on that decision and are small on their own:

- **A2 — Langfuse.** Stop sending `langfuse_user_id`, mask content at source, or add a
  deletion call to the cascade. The highest-impact finding.
- **A4 — mem0 failure is silent.** `delete_user_memory` swallows its exception, so a
  failed deletion reports success. Make it propagate, as checkpoint deletion does.

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
**Owned by** roadmap step 3, Chat screen. **Unblocks:** the assistant in production. **Done when** a mid-stream disconnect stops the
LLM call promptly, and the event shape and the middleware behaviour on the route are
unchanged.

## Server — row-level security

Ownership is enforced in the query layer: every user-owned repository method filters by
`user_id`. A forgotten filter is a cross-user read, caught today only by review and by
`test_owned_tables.py` checking that every table uses `UserOwnedMixin` — not that its
queries filter. Postgres RLS keyed on a per-transaction user id would make the database
refuse the read instead. **Blocked by** the superuser role in [`BUGS.md`](./BUGS.md): a
role with `BYPASSRLS` ignores every policy. **Unblocks:** defence in depth for the first
finance table.

## Web — tests the suite does not have yet

- **`QueryProvider`'s error policy.** Which queries toast (never-resolved only, unless
  `silentError`), that mutations always do, and that a 4xx is not retried. The mutator and
  the status-recovery hook are covered; the provider that applies their errors is not.
- **End to end.** Nothing drives a browser. The `.spec.` suffix and the `e2e/**` exclude
  are reserved for Playwright; the first flow worth it is sign-up and sign-in through to a
  real screen.

Reasoning: [`architecture/web-app.md`](./architecture/web-app.md) §7.

## Web — the transactions empty state, with CSV import (roadmap step 4)

With no transactions the page offers **Add a transaction**. When CSV upload ships, the
prompt becomes **Upload a CSV** (`transactions.md` §2).

**Unblocks:** nothing; it lands with step 4.

## Port — carry into backend modules

Defects in the legacy app (`../pf-legacy/docs/TODO.md`) that the port should not repeat
when it rebuilds each module. One line each, pointing at the legacy file, and the roadmap
step that owns it.

- **Services returning `None` on a miss** (step 4) — `CSVMappingService.get_session` returns
  `None` and the route checks; raise a not-found error in the service instead.
  `server/app/services/csv_mapping/service.py`.
- **Direct `ChatOpenAI` use** (step 4) — the CSV column-mapping proposal builds its own client,
  bypassing the LLM service's retries, model fallback and error translation. Go through
  the LLM service. `server/app/api/v1/transactions.py` (`_propose_column_mapping`).

## Cutover (roadmap step 8)

Facts that exist only because the app was ported from a legacy codebase:

- The legacy app runs from the `../pf-legacy` worktree at tag `legacy-v0`.
- Never run it while this stack is up: both publish port 3000.
- Keep the legacy OAuth redirect URI on the shared Clerk OAuth client until cutover, then
  remove it.
