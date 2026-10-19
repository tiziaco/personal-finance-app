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

## Server — no request-body size limit ahead of FastAPI

Starlette spools a multipart body to disk in full before auth, the rate limiter or the route
run. The import's 5 MB check bounds only what the route reads into memory, and an
unauthenticated multi-GB upload is accepted onto disk before its 401.

**Fix:** an ASGI middleware that rejects on `Content-Length` and counts streamed bytes, or a
body limit at the proxy (`docker-compose.prod.yml` sets none). **Found:** step 4.

## Server — row-level security

Ownership is enforced in the query layer: every user-owned repository method filters by
`user_id`. A forgotten filter is a cross-user read, caught today only by review and by
`test_owned_tables.py` checking that every table uses `UserOwnedMixin` — not that its
queries filter. Postgres RLS keyed on a per-transaction user id would make the database
refuse the read instead. **Blocked by** the superuser role in [`BUGS.md`](./BUGS.md): a
role with `BYPASSRLS` ignores every policy. **Unblocks:** defence in depth for the first
finance table.

## Server — a model call holds the request's DB connection

`POST /chatbot/chat/{id}` and `POST /conversation/conversation/{id}/title` load the
conversation through `UserConversation`, which opens the request's `DbSession`
transaction, then await a model call of several seconds before the session commits after
the route. The pool connection sits idle in transaction for that long. Fine at one user's
traffic; under concurrent chats it starves other requests of connections. The fix is to
read what the call needs, release the session before the model call, and write with a
short-lived session from `request.app.state.session_factory`, as a streaming body already
must (`server/CLAUDE.md`, Code Conventions). The import routes and `POST /insights/generate` already release it
(`_release_connection` in `transaction/imports/service.py` and `insights/service.py`). **Unblocks:** chat under concurrent load.

## Server — a transaction added by hand is not held to the date bounds

The import rejects a row dated outside `MIN_DATE`/`MAX_DATE`
(`transaction/domain/dates.py`), but a transaction added or edited by hand is not held to
them, so a typo year drops out of every chart without a word, as the import's did. Validate
the date on create and update against the same bounds. Found while fixing the import's
(15 Oct 2026).

## Server — the chatbot names the default model after a fallback

After an LLM fallback, the chatbot's inference-time metric label and its stored model name
are the default model's (`current_model_name()`), not the one that answered. `LLMService`
keeps no fallback position on itself any more, by design; the answering model is in the
response's `response_metadata`. Read it from there. Found while making the fallback
per call (15 Oct 2026).

## Server — every LLM call starts at the default model

Each call walks the registry from the default model, so while the default is down every
chat turn and labelling batch spends its retries there first (three attempts, about 2 s
apart) before falling back. It is the cost of keeping the position per call, which
concurrent calls need (15 Oct 2026). If it matters, keep a short-lived "last model that
answered" hint on the service and start unpinned calls there.

## Server — CSV import follow-ups

- During an LLM outage every labeller batch walks the full model fallback chain before
  failing, so a large file takes several waves to become a 503. Stop launching batches once
  the first wave has all failed.
- `profile_columns` and `read_rows` are synchronous CPU work on the event loop (about 0.6 s
  for 3,000 rows × 12 columns). Move them to `run_in_threadpool` if traffic grows.
- A short DKB export whose preamble lines outnumber its transactions is refused as
  `unnamed_column`, because the most common line width is the preamble's.

## Server — income and expense are decided by the sign of the amount alone

A refund counts as income, and a transfer to savings or an ATM withdrawal as spending, in
every analytics figure (`analytics.md` §4). Found in the 5b legacy audit. **Unblocks:**
figures that match what the user means by income and spending. **Needs:** a transfer/refund
notion on `transaction`.

## Server — a per-user cap on insight generation

Every `POST /insights/generate` is a paid model call over the user's figures, and opening
`/insights` on a stale set calls it too. Today only the per-user rate limit of 10 a minute
guards it — a runaway-click guard, not a budget — and step 6 deliberately set no cooldown or
daily cap (16 Oct 2026). Before public sign-up, cap generations per user (a daily count, or a
cooldown when the set is fresh), answered with an error the page can show by the Regenerate
button. **Unblocks:** public sign-up without an open-ended LLM bill. Reasoning:
[`product/features/insights.md`](./product/features/insights.md) §4–5.

## Web — tests the suite does not have yet

- **A failed conversation create.** In `ChatRuntimeProvider`, a create that answers 500
  clears the exchange and gives the text back to the composer if the user is still there.
  The provider restructure moved this into `ensureConversation`; no test exercises it.
- **End to end.** Nothing drives a browser. The `.spec.` suffix and the `e2e/**` exclude
  are reserved for Playwright; the first flow worth it is sign-up and sign-in through to a
  real screen.
- **The home trend chart's tooltip cursor.** It keeps recharts' default cursor, which
  `chart-parts` documents as a bright band in dark mode; adopting `LINE_TOOLTIP`'s cursor is
  a visible change to make on purpose.

Reasoning: [`architecture/web-app.md`](./architecture/web-app.md) §7.

## Web — legacy's theme

Step 2 brought back legacy's layout on `/transactions` — the table card, the filter sheet, the
floating bulk bar, the sort control — but not its theme: the teal accent, the grey-green page
background and the font. The theme changes every page, so it is a decision of its own, made
once for the whole app, not per screen. Corners are already decided, against legacy's pills:
one radius scale, in the `web-app-patterns` skill's `references/components.md`. Legacy's
calendar date-range picker is out too; the date filter uses the shared single-day picker. Reference screenshots of both apps were taken with the same
data on 14 Oct 2026.

**Unblocks:** nothing; the app is usable with the template's theme.

## Server — a yearly charge is recurring only after three years (roadmap row "Analytics rules")

Surfaced by step 6's insights run. Correct by the current rule, but the rule may be wrong
for the user. `CADENCES` in `server/app/modules/transaction/domain/recurring.py` gives
`yearly` a `min_rows` of 3, so an annual subscription (Amazon Prime) seen once or twice is
not flagged. `analytics` recurring can already price one (`interval_days`, €600 a year shows
as €50 a month) once it is flagged. Decide whether two yearly charges at one amount are
enough, or whether only the user's flag marks one.

## Server — analytics loads the whole history on every request

Every `AnalyticsService` method loads the user's entire transaction history
(`transaction_service.list_for_analysis` from `MIN_DATE` to `MAX_DATE`, in
`AnalyticsService.history`, which builds `AnalyticsHistory`), whatever period it was asked
for. `AnalyticsHistory` fixes the fan-out inside one caller that needs several windows (an insights generation) but not across
requests: the home dashboard, each `/analytics` tab and each period change are separate
requests, and each reads every row again. Fine at one user's data; it grows with the history
and with every caller step 7 adds.

**Fix:** cache a user's analysis rows on the server, keyed by `user_id`, and drop the entry
whenever that user's transactions change. **Decide first:**

- **Where it lives.** In-process (one uvicorn process today, no Redis in the stack) is
  enough until there is more than one worker; a shared cache is then a new service.
- **What is cached.** The rows (every method still computes, one invalidation rule) or each
  response (cheaper hits, but keyed by period and today too).
- **How it is invalidated.** `transaction` publishes only `TRANSACTIONS_ALL_DELETED`
  today. A create, edit, delete, import or recurring refresh must drop the entry, so either
  `transaction` publishes a "transactions changed" event that `analytics` subscribes to, or
  each user carries a data version that the cache key includes. A TTL alone would show a
  stale chart right after an edit.

**Unblocks:** analytics and chat that stay fast as a user's history grows. **After:**
nothing; `AnalyticsHistory` is the one load to cache. Found while scoping it (19 Oct 2026).

## Web — analytics page parts

- Promote the analytics page's `Section`, `Change` and `PeriodSelect` to `@app/ui` if a
  second screen wants them.

## Cutover (roadmap step 8)

Facts that exist only because the app was ported from a legacy codebase:

- The legacy app runs from the `../pf-legacy` worktree at tag `legacy-v0`.
- Never run it while this stack is up: both publish port 3000.
- Keep the legacy OAuth redirect URI on the shared Clerk OAuth client until cutover, then
  remove it.

## Web — the currency symbol

Money shows in EUR everywhere: `formatAmount` in
`apps/web/src/components/transactions/format.ts` hard-codes it. `analytics.md` §4 promises the
symbol the user picks in Settings. The setting is display only — amounts are stored without a
currency. **Unblocks:** a user outside the euro area. **Decide first:** where the preference
lives (the user row, or the browser).

## Web — a month picker on the dashboard

The home dashboard shows the latest finished month with data (decided 15 Oct 2026 as the
latest month with data; reversed on 16 Oct 2026: partial months read as a collapse).
A picker would let the user look back; every analytics route already takes
`date_from`/`date_to`, but `GET /analytics/dashboard` picks its own month, so it gains a
`month` parameter. **Unblocks:**
looking at a past month without the analytics page. Reasoning: `analytics.md` §6.

## Server — a merchant the user unflagged can be suggested as a hidden subscription

A hidden subscription is a merchant never flagged recurring in the user's history. Analytics'
rows do not carry `recurring_source`, so a merchant the user explicitly unflagged
(`recurring_source = USER`) can still be suggested. Fixing it needs the transaction module's
`AnalysisRow` to expose `recurring_source`. **Unblocks:** a hidden-subscription list that
respects the user's "not recurring". Reasoning: `analytics.md` §3.

## Chat — free-form questions over the user's data

The chat tools (step 7) call the analytics library's fixed functions. A question they do not
cover could be answered by generated code run in an isolated sandbox with its own environment
(polars or similar); the server only hands it the user's rows from
`transaction_service.list_for_analysis`, as CSV or JSON, so no dataframe library enters
`server/pyproject.toml`. **Unblocks:** open-ended questions in chat. Decided with step 5a
(15 Oct 2026): the server library stays plain Python.
