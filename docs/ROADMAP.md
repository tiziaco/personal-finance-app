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
| **5b Analytics page** — the four `/analytics` views | not started | — | [`analytics.md`](./product/features/analytics.md). No spec yet |
| **6 Insights** — generation, the `/insights` page and the dashboard callout | not started | — | [`insights.md`](./product/features/insights.md). No spec yet |
| **7 Chat finance tools** — the assistant answers questions about the user's own money | not started | — | [`chat.md`](./product/features/chat.md). No spec yet |
| **8 Cutover** — merge into `main`, retire legacy | not started | — | [`TODO.md`](./TODO.md) **Cutover** |

Everything else outstanding is in [`BUGS.md`](./BUGS.md) (wrong today) or
[`TODO.md`](./TODO.md) (deferred to the change that should make it). An item gets a row
here when someone picks it up.

### Ordering notes

**The port (steps 2–7).** Every finance step but the first can share a wave:

| Wave | Steps, in parallel | Starts when |
|---|---|---|
| 1 | 2 Transactions ∥ 3 Chat screen | done — #11, #12 merged into `template-base` |
| 2 | 4 CSV import ∥ 5a Analytics dashboard | in progress (2 has merged) |
| 3 | 5b Analytics page ∥ 6 Insights ∥ 7 Chat finance tools | 5a has merged |

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
- **6 and 7 wait for 5a** (technical). The insights graph calls all eight library
  functions, and its callout goes on the home page 5a builds. The chat tools wrap the
  library; `app.agents` may not import a module (contract R2), so they are built in a
  module and injected, which is 7's main design question.

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
