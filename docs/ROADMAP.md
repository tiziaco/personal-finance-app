# Roadmap

Where the work stands, and in what order it happens. **This is the only file in the
repo that records progress.** Everything else records reasoning, and a document that
carries both goes stale in the half a reader cannot check.

- **A spec says why** — `.superpowers/specs/*.md`, while its change is in flight. In the
  PR that merges it, what lasts moves into the docs and the spec is deleted.
- **A plan says how** — `.superpowers/plans/*.md`. Its `- [ ]` checkboxes are the
  task-level ledger for its branch, and it is deleted in the same PR.
- **This file says where we are** — one row per change in flight, updated in the same
  commit (or the same PR) as the work that moves it.

**States:** `not started` → `in progress` → `complete`, plus `deferred` and `blocked`, each
with a reason. A row is deleted in the PR that merges its change to `main`, not when its branch
is green. What shipped is in `git log`.

Links are relative to `docs/`.

---

## Open

| Change | State | Branch | Where it is specified |
|---|---|---|---|
| **1 Foundation** — single-tenant B2C base | complete — [PR #9](https://github.com/tiziaco/personal-finance-app/pull/9) into `template-base`; reaches `main` at Cutover | `port/template` | [`architecture/`](./architecture/), [`setup/clerk.md`](./setup/clerk.md) |
| **2 Transactions** — the `transaction` table and the category list; browse, filter, add, edit, delete and recategorise by hand; fixes the email-uniqueness lockout | complete — [PR #12](https://github.com/tiziaco/personal-finance-app/pull/12) into `template-base`; reaches `main` at Cutover | `feat/transactions` | [`transactions.md`](./product/features/transactions.md), [`categorisation.md`](./product/features/categorisation.md) (correcting a category), [`data-model/transaction.md`](./data-model/transaction.md), [`data-model/account.md`](./data-model/account.md) D3 (email not unique) |
| **3 Chat screen** — the conversations UI on the existing `conversation` module; stops the stream on a client disconnect (WS7); moves the LLM provider to OpenRouter | complete — [PR #11](https://github.com/tiziaco/personal-finance-app/pull/11) into `template-base`; reaches `main` at Cutover | `feat/chat-screen` | [`chat.md`](./product/features/chat.md), [`data-model/conversation.md`](./data-model/conversation.md) |
| **4 CSV import** — upload, mapping review and import, each row categorised by the AI labeler; the recurring-detection rule that sets `is_recurring` | complete — [PR #14](https://github.com/tiziaco/personal-finance-app/pull/14) into `template-base`; reaches `main` at Cutover | `feat/csv-import` | [`csv-import.md`](./product/features/csv-import.md), [`categorisation.md`](./product/features/categorisation.md), [`data-model/transaction.md`](./data-model/transaction.md) D6–D9 |
| **5a Analytics dashboard** — the whole computation library and the home dashboard | complete — [PR #13](https://github.com/tiziaco/personal-finance-app/pull/13) into `template-base`; reaches `main` at Cutover | `feat/analytics-dashboard` | [`analytics.md`](./product/features/analytics.md) |
| **Fixes before wave 3** — the 401 race after sign-in; `LLMService`'s shared fallback state; the import rejects dates analytics cannot read; fixed income and expense chart colours | complete — [PR #15](https://github.com/tiziaco/personal-finance-app/pull/15) into `template-base`; reaches `main` at Cutover | `fix/pre-wave-3` | [`authentication.md`](./architecture/authentication.md) §2–3, [`web-app.md`](./architecture/web-app.md) §4–5, [`server.md`](./architecture/server.md) (the error table), [`csv-import.md`](./product/features/csv-import.md) |
| **Analytics figures** — the category-growth fix and every derived figure the `/analytics` page shows, computed by the server | complete — [PR #16](https://github.com/tiziaco/personal-finance-app/pull/16) into `template-base`; reaches `main` at Cutover | `feat/analytics-figures` | [`analytics.md`](./product/features/analytics.md) §2–3 |
| **5b Analytics page** — the four `/analytics` views | complete — [PR #17](https://github.com/tiziaco/personal-finance-app/pull/17) into `template-base`; reaches `main` at Cutover | `feat/analytics-page` | [`analytics.md`](./product/features/analytics.md) §2 |
| **6 Insights** — generation, the `/insights` page, the dashboard callout and the home month-to-date card | complete — [PR #18](https://github.com/tiziaco/personal-finance-app/pull/18) into `template-base`; reaches `main` at Cutover | `feat/insights` | [`insights.md`](./product/features/insights.md), [`data-model/insight.md`](./data-model/insight.md), [`transaction.md`](./data-model/transaction.md) D4 (the delete-all event) |
| **Wave 3 cleanup** — shared analytics plumbing the 5b and 6 reviews found: url-state exports, chart props, two loading fixes on Income vs Expenses, one history load per caller, the month-to-date rule in one place; plus the status-dot ring, the rate-limit test fixture and the QueryProvider retry test | complete — [PR #20](https://github.com/tiziaco/personal-finance-app/pull/20) into `template-base`; reaches `main` at Cutover | `feat/wave3-cleanup` | [`analytics.md`](./product/features/analytics.md) §3 (no average without a whole month; month-to-date); [`architecture/server.md`](./architecture/server.md) (`AnalyticsHistory`) |
| **Analytics rules** — an outlier rule for a thin category, frequent shopping not flagged recurring, yearly charges, hidden subscriptions that respect the user's "not recurring", and date bounds on hand-added transactions | complete — [PR #19](https://github.com/tiziaco/personal-finance-app/pull/19) into `template-base`; reaches `main` at Cutover | `feat/analytics-rules` | [`analytics.md`](./product/features/analytics.md) §3, [`data-model/transaction.md`](./data-model/transaction.md) D6, [`csv-import.md`](./product/features/csv-import.md) |
| **Design system** — the app restyled to the design system made in Claude Design: tokens (colour in both themes, type, spacing, radius), fonts and the shared primitives, so every screen follows | complete — [PR #21](https://github.com/tiziaco/personal-finance-app/pull/21) into `template-base`; reaches `main` at Cutover | `feat/design-system` | [`web-app.md`](./architecture/web-app.md) §2 (the design system); the `finsight-design` skill; supersedes the former TODO **Web — legacy's theme** |
| **7 Chat finance tools** — the assistant answers questions about the user's own money, shows its lookups and thinking, and releases the request's DB connection before a model call | complete — [PR #22](https://github.com/tiziaco/personal-finance-app/pull/22) into `template-base`; reaches `main` at Cutover | `feat/chat-finance-tools` | [`chat.md`](./product/features/chat.md), [`architecture/server.md`](./architecture/server.md) (agents get module knowledge by injection) |
| **7b Agent core** — the chat agent on LangChain 1.3's `create_agent`, tools as `StructuredTool`s with a typed turn context, middleware for the step cap, wrap-up, context editing and memory; `agents/` reshaped into `core/` plus one package per agent; the chat's wire types owned by `conversation`. Behaviour unchanged: same stream, same history, same tool results | complete | `refactor/agent-core` | [`architecture/server.md`](./architecture/server.md) §1, [`chat.md`](./product/features/chat.md) §4; [`TODO.md`](./TODO.md) **one-call agents on with_structured_output** |
| **8 Cutover** — merge into `main`, retire legacy | not started | — | [`TODO.md`](./TODO.md) **Cutover** |
| **9 Chat evaluation** — an eval set of questions over a seeded account, a grounding check that every figure in an answer came from a tool result, and an LLM-as-judge for answer quality; builds on the Langfuse traces of tool calls | not started | — | [`chat.md`](./product/features/chat.md) §4 (figures come from tools). No spec yet |

Everything else outstanding is in [`BUGS.md`](./BUGS.md) (wrong today) or
[`TODO.md`](./TODO.md) (deferred to the change that should make it). An item gets a row
here when someone picks it up.

### Ordering notes

**The port (steps 2–7).** Every finance step but the first can share a wave:

| Wave | Steps, in parallel | Starts when |
|---|---|---|
| 1 | 2 Transactions ∥ 3 Chat screen | done — #11, #12 merged into `template-base` |
| 2 | 4 CSV import ∥ 5a Analytics dashboard | done — #13, #14 merged into `template-base` |
| 3 | Analytics figures ∥ 5b Analytics page ∥ 6 Insights | done — #16, #17, #18 merged into `template-base` |
| 4 | Wave 3 cleanup ∥ Analytics rules | done — #19, #20 merged into `template-base` |
| 5 | Design system | done — #21 merged into `template-base` |
| 6 | 7 Chat finance tools | done — [PR #22](https://github.com/tiziaco/personal-finance-app/pull/22) into `template-base` |
| 7 | 7b Agent core | after #22 |

A step starts when the steps it needs have merged, not when its whole wave has: 5b does
not wait for 4.

- **Transactions comes first** (technical). Every finance step reads or writes the
  `transaction` table and its category list. Built in parallel, each would invent its own.
- **The email-uniqueness fix rides in Transactions** (technical; placed there by decision
  on 13 Oct 2026). The choice changes the migration, so it is settled before the first
  table references `user`.
- **Chat screen runs beside Transactions** (technical). It touches only the
  `conversation` module and the sidebar, and needs nothing from the finance steps.
- **CSV import includes AI categorisation** (product, 13 Oct 2026): an import arrives
  categorised. The labeler has no other caller, so as its own step it could not be demoed.
- **Recurring detection rides in CSV import** (technical; decision on 15 Oct 2026). The
  stored `is_recurring` flag is the one source of truth: one deterministic rule in
  `transaction` sets it after every write, a user's edit is never overwritten, and every
  reader (the dashboard card, insights, the chat tools) reads the flag rather than
  detecting recurrence itself. The rule is on `transaction`'s write path, which step 4 owns.
- **5a needs only Transactions, so it runs beside CSV import** (technical). Transactions
  added by hand, or by a seed script, are enough data.
- **5a carries the whole computation library** — merchants, recurring, anomalies and
  stability too, which have no screen of their own (technical; decision on 13 Oct 2026).
  Insights and the chat tools call them, so shipping them in 5a lets 5b, 6 and 7 run
  together. In 5b they would serialise 6 and 7 behind it.
- **A round of fixes comes between waves 2 and 3** (decision on 15 Oct 2026). The 401
  race shows on `/transactions` today, and wave 3 adds two more LLM callers, so the shared
  `LLMService` fallback state is fixed before they arrive. The chart colours go in the same
  change because 5b needs them.
- **6 and 7 wait for 5a** (technical). The insights graph calls all eight library
  functions, and its callout goes on the home page 5a builds. The chat tools wrap the
  library; `app.agents` may not import a module (contract R2), so they are built in a
  module and injected, which is 7's main design question.
- **The Tabs primitive went in ahead of wave 3** (technical; 16 Oct 2026). 5b and 6 both
  have tabbed pages; built in each branch, the same new file would conflict.
- **7 wraps only the analytics library, not the stored insights** (product; 16 Oct 2026).
  `conversation` does not import `insights`, so 7 does not wait for 6. A tool that reads
  insights is a follow-up.
- **7 waits for the Wave 3 cleanup** (decision on 17 Oct 2026). It launched with wave 3 but
  was closed before its spec. The cleanup added `AnalyticsService.history`, which loads a
  user's history once and returns a typed `AnalyticsHistory`; 7's tools build on that, rather
  than on methods that each reload the whole history.
- **Evaluation is its own step after 7** (product; decision at the 7 brainstorm, 20 Oct 2026).
  7 ships the tools and leaves their Langfuse spans (arguments and results) as the raw
  material; the eval set, grounding check and judge need the finished tools and a stable
  prompt, so building them inside 7 would be graded against a moving target.
- **Evaluation comes after Cutover** (product; decision on 20 Oct 2026). It has no technical
  dependency on 8 either way, so the order is a product choice.
- **7b Agent core comes between 7 and Cutover** (product; decision on 21 Oct 2026). Step 7's
  reviews found the agent package hand-rolls what LangChain 1.3 ships (the tool loop, context
  editing, the tool contract and context injection) and that the generic layer imports one
  agent's package. Rebuilt on the library before Cutover, `main` receives the final loop and
  Evaluation (9) is written against it rather than against a loop about to change: the eval
  set reads the stream and checkpoint shapes 7b touches. Cutover has no technical dependency
  on 7b; it waits by choice, as it did for the Wave 3 cleanup.
- **Analytics rules is its own step, beside the cleanup** (product and technical; decision
  on 19 Oct 2026). The cleanup changes no behaviour; the rules step changes what the library
  reports, and may re-judge stored recurring flags, so the two are reviewed apart. They run
  in parallel on these conditions: the rules step stays out of `analytics/service.py`,
  `domain/spending.py`, `MonthToDateResponse` and `insights/`; the cleanup stays out of
  `domain/anomalies.py`, `domain/recurring.py` and the whole `transaction` module; a new
  `AnalysisRow` field has a default; only the cleanup edits `server/tests/conftest.py`. The
  generated client, `analytics.md` and the TODO and BUGS lists merge mechanically. 7 does
  not need the rules technically, but without them its answers repeat the wrong outliers
  and flags.
- **The chat-side TODOs ride in 7** (technical; decision on 19 Oct 2026). The model name
  after a fallback and the DB connection held through a model call change the chat route
  and graph that 7 changes. Releasing the request's session before the model call is the
  same question as how 7's tools get a session, so one spec settled both; both are done in 7.
- **The design system comes before 7** (product; decision on 19 Oct 2026). It restyles
  every screen, the chat included, so the two do not run in parallel. Step 7 may add chat UI
  (a tool call shown in the thread); built after the restyle, it starts on the new tokens
  rather than being restyled a second time.
- **The design system supersedes "legacy's theme"** (product; 19 Oct 2026). That TODO
  deferred the theme to one decision for the whole app; this step is the decision, and its
  PR deletes the entry. The radius scale in `web-app-patterns`' `references/components.md`
  was decided against legacy's pills; the design system replaces it only on the user's word,
  in the step's spec. Standalone Claude Design closes on 14 Dec 2026, so what the app keeps
  from the design system (its tokens and rules) lands in the repo, not only in that project.
- **Analytics figures is its own step, ahead of 5b's page** (product; 16 Oct 2026). The
  page computes nothing: every figure it shows comes from the server, and the category
  growth measure is fixed there (earlier half of the range against the later half, not
  first month against last). 6 and 7 build on the same module, so one step owns it and
  merges first; the others merge `template-base` after it.
- **Analytics periods are finished months** (product; 16 Oct 2026). Every analytics range
  is whole finished months, with the month in progress shown apart as month-to-date. Imports
  lag the calendar, and a partly filled month read as a collapse in spending. This reverses
  the dashboard decision of 15 Oct 2026 (the latest month with data).

### Running a wave in parallel

The `orchestrator` skill runs it: one coordinator session in the main checkout, one
worker session per step in its own worktree and iTerm2 tab. The `worktrees` skill has the
ports and slots. Until Cutover, **`template-base` stands in for `main`** wherever those
skills say `main`: branches are cut from it, PRs target it, and the main checkout sits on
it.

1. Merge the steps the wave needs, and bring the main checkout to a clean
   `template-base`.
2. Start the coordinator there (`claude -n orchestrator`) and ask it to launch the wave.
   It sets the wave's rows to `in progress` in one commit, then per step runs
   `git branch feat/<name> template-base && make worktree-new NAME=<name>` and opens a
   worker tab with a brief.
3. In each worker tab, brainstorm the spec with the worker, approve its plan, and let it
   execute up to an open PR. The worker sets its row to `complete` in that PR; rows are
   deleted at Cutover, when the change reaches `main`.
4. Merge one PR at a time. After each merge, the remaining workers merge
   `template-base` into their branch and resolve the files every step touches:
   - **Alembic** — re-point the later migration's `down_revision` at the merged head;
     `alembic/env.py` takes both imports.
   - **`server/pyproject.toml`** — each new module's R1 contract must forbid every other
     module, so take the union of both sides; a one-sided resolve fails
     `test_module_contracts.py`. Regenerate `uv.lock` rather than merging it.
   - **The API contract** — take either side and run `make gen-contract`.
   - **`hub-nav.ts`, the `packages/ui` barrel, `pnpm-lock.yaml`** — union, then
     regenerate the lockfile.
5. Tear down each merged step's worktree with `make worktree-clean`, never `make clean`.

**Elsewhere.** The dependencies already recorded in [`BUGS.md`](./BUGS.md) and
[`TODO.md`](./TODO.md), gathered in one place:

- **The database role split comes before row-level security.** A role with `BYPASSRLS`
  ignores every policy ([`BUGS.md`](./BUGS.md), [`TODO.md`](./TODO.md)).
- **Before the first deploy behind Traefik:** `--forwarded-allow-ips`, or every caller
  shares one rate-limit bucket.
