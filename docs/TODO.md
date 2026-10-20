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
role with `BYPASSRLS` ignores every policy. **Unblocks:** defence in depth for the finance
tables.

## Insights — word an outlier by what it was compared with

Since 19 Oct 2026 an outlier carries `compared_with`, and the insights agent already receives
it (`insights/figures.py` passes the anomalies through `model_dump`). What is missing is the
wording: the prompt (`server/app/agents/insights/prompts/v1.md`, the `anomalies` section line,
"a single unusual charge") never tells the model that `"all"` means the expense was scored
against all one-off spending, to be worded "above your usual spending" rather than "above its
category". Owned by whoever next touches the insights prompt.

## Server — a fixed cost not yet flagged recurring is an outlier

An expense whose category's window holds fewer than 5 expenses is compared with all one-off
spending (`analytics/domain/anomalies.py`, since 19 Oct 2026). Rent the recurring rule has not
flagged yet — two months imported, when the monthly cadence needs three rows, or a payee whose
merchant key changes each month — is such an expense: €1,200 against daily groceries scores
a z of about 170. Ticking the row recurring clears it, and so does a third month. Left as is
because, until then, rent looks exactly like a one-off; excluding `household_utilities` from
the fallback would also hide a large furniture or appliance purchase. Revisit if users report
it, for instance by not falling back for a charge the same merchant made about a month earlier.

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

## Server — a transaction counted in the month it belongs to

A salary paid on the 1st instead of the 30th leaves its month with no income and the next
with two, so both months' savings rates are wrong; one month with only a small refund as income
reads −15,000%. The savings rate stays net over income for the month (decided 20 Oct 2026):
smoothing it with a rolling window lags, and dividing by an average income stops measuring
what happened. Re-dating the transaction, which Copilot, PocketGuard and Simplifi users do,
falsifies the bank date. **Fix:** an optional month on `transaction` that the user sets
("count in September") and every analytics month bucket reads instead of `date`'s month;
the transactions table and the import keep the bank date. **Unblocks:** monthly figures
that survive a late salary. **Needs:** a data-model decision in `transaction.md` and an
action on the transactions page.

## Server — a per-user cap on insight generation

Every `POST /insights/generate` is a paid model call over the user's figures, and opening
`/insights` on a stale set calls it too. Today only the per-user rate limit of 10 a minute
guards it — a runaway-click guard, not a budget — and step 6 deliberately set no cooldown or
daily cap (16 Oct 2026). Before public sign-up, cap generations per user (a daily count, or a
cooldown when the set is fresh), answered with an error the page can show by the Regenerate
button. **Unblocks:** public sign-up without an open-ended LLM bill. Reasoning:
[`product/features/insights.md`](./product/features/insights.md) §4–5.

## Web — tests the suite does not have yet

- **End to end.** Nothing drives a browser. The `.spec.` suffix and the `e2e/**` exclude
  are reserved for Playwright; the first flow worth it is sign-up and sign-in through to a
  real screen.

Reasoning: [`architecture/web-app.md`](./architecture/web-app.md) §7.

## Server — analytics loads the whole history on every request

Every `AnalyticsService` method loads the user's entire transaction history
(`transaction_service.list_for_analysis` from `MIN_DATE` to `MAX_DATE`, in
`AnalyticsService.history`, which builds `AnalyticsHistory`), whatever period it was asked
for. `AnalyticsHistory` fixes the fan-out inside one caller that needs several windows (an insights generation) but not across
requests: the home dashboard, each `/analytics` tab and each period change are separate
requests, and each reads every row again. Fine at one user's data; it grows with the history
and with every caller the chat tools add.

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
nothing; `AnalyticsHistory` is the one load to cache. Found while scoping the Wave 3 cleanup (19 Oct 2026).

## Web — analytics page parts

- Promote the analytics page's `Section`, `Change` and `PeriodSelect`/`PeriodHeader` to
  `@app/ui` if a second screen wants them. The home dashboard already reaches into
  `components/analytics/` for `chart-parts.tsx` and `stale-time.ts`; move those to a
  shared home when the parts move.
- **The home trend chart's tooltip cursor.** It keeps recharts' default cursor, which
  `chart-parts` documents as a bright band in dark mode; adopting `LINE_TOOLTIP`'s cursor is
  a visible change to make on purpose.

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

## Chat — conversation summaries

A very long conversation drops its oldest turns from what the model is sent, oldest first,
once the history passes `CHAT_HISTORY_MAX_TOKENS`; nothing stands in for them, so the
assistant forgets how it began. Summarising the dropped turns (into the checkpoint, or
beside it) would keep the thread. Left out of step 7 by decision (20 Oct 2026).
**Unblocks:** long-running conversations. Reasoning: [`product/features/chat.md`](./product/features/chat.md) §4.

## Chat — free-form questions over the user's data

The chat tools call the analytics library's fixed functions. A question they do not
cover could be answered by generated code run in an isolated sandbox with its own environment
(polars or similar); the server only hands it the user's rows from
`transaction_service.list_for_analysis`, as CSV or JSON, so no dataframe library enters
`server/pyproject.toml`. **Unblocks:** open-ended questions in chat. Decided with step 5a
(15 Oct 2026): the server library stays plain Python.
