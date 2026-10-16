# Step 6 Insights — design

**Roadmap row:** 6 Insights · **Branch:** `feat/insights` · **PR into:** `template-base`
**Product doc:** [`docs/product/features/insights.md`](../../docs/product/features/insights.md) — this
spec changes several of its rules; the doc is rewritten to match in the PR that ships.
**Ownership and conditions:** `.superpowers/BRIEF.md` §3 (not repeated here; it binds).

---

## 1. Intent

The dashboard and the analytics page show numbers. Insights are a short **written reading** of
those numbers: what stands out this month, why it matters, and sometimes what to do about it.

Legacy v1.0 did not do this. It filled at most seven fixed templates with figures (top
category, recurring share, MoM growth, weekend bias, merchant concentration, stability,
outliers) and asked the model only for a two-sentence paragraph under each, one call per card.
Every user saw the same seven cards; two templates printed literal `$X`/`$Y`; amounts used `$`
in an EUR app; the Generate button re-read a cache that only refreshed on *added* transactions,
behind a one-hour browser timer.

The user chose (16 Oct 2026) to have **the model choose and write the insights** from the
analytics figures, in one call, while keeping **the same kinds of observation** legacy made.

**The user's routine** decides most of the rules below: they open the app once a week or once a
month, upload that period's CSV (sometimes add a transaction by hand), and look at how the
period went.

## 2. Goals, non-goals, anti-goals

**Goals**

- Insights about **the last finished month against your usual**, plus one or two on **how the
  current month is going so far**, written by the model from computed figures, sorted by
  importance, in the five sections legacy had.
- Fresh after the user's data changes, with no thought from the user: upload, open Insights,
  read.
- A Regenerate button that always produces a new reading.
- A home callout with the top three, which never makes the home page wait on the model.

**Non-goals (this step)**

- The savings tracker (a checklist of actions). Savings stays text.
- Any limit on Regenerate beyond the app's ordinary rate limit (§6.4). A per-user cap waits for
  public sign-up; a `TODO.md` entry records it.
- The chat assistant reading stored insights (decided 16 Oct 2026; `conversation` does not
  import `insights`).
- Alerts, goals, acting on an insight, sharing, history of past sets.
- Settling Langfuse tracing of the user's figures (`TODO.md`, Erasure A2): proceed as today.

**Anti-goals — it fails even if it works when:**

- A card states a figure that is not in what the model was given (an invented amount, a wrong
  merchant). The model narrates; it never computes.
- The home page waits on, or triggers, a model call.
- A failed generation leaves the user with an empty page where a previous set existed.
- Cards read as generic advice ("consider budgeting") rather than about *their* month.
- Amounts appear in anything but EUR. (The key-figure chip is formatted by the web in the
  browser's locale, like every other amount in the app; prose amounts are written by the model in
  one fixed form — §5.3.)

## 3. What the user sees

Mockups agreed in the brainstorm (option B for the page; the callout as shown).

### 3.1 `/insights`

- **Header:** title "Insights", a one-line description, and on the right **"Generated
  16 Oct 2026, 14:32"** beside a **Regenerate** button. While a generation runs the button reads
  "Generating…" and is disabled.
- **Tabs** (the `@app/ui/tabs` primitive already on `template-base`): **All** first, then
  **Spending, Recurring, Savings, Anomalies, Comparisons**, each with a count. All lists every
  card sorted by severity (high → info; ties keep the model's order). A tab with no cards says so
  in one line.
- **A card:** the summary as its title (one sentence); the narrative (one to three sentences);
  a **key-figure chip** ("€184 / month", "+87% vs usual"); a severity label; on All, its section
  tag; and, where it has one, a **link** to the related transactions (§5.3).
- **Arriving with no set, or a stale one** (§4): the page shows the previous cards, if any,
  under a loading state and generates at once; the user waits (expected 10–30 s).
- **No transactions:** an empty state pointing at the CSV upload. No model call.
- **Generation fails:** the previous set stays on screen, with an error by the button. With no
  previous set, the page shows the error and a retry.
- **Sidebar:** an **Insights** entry after Analytics, before Chat (order decided: Home,
  Transactions, Analytics, Insights, Chat). 5b adds Analytics in its own branch; the merge keeps
  both.

### 3.2 Home callout

- Full width, between the charts and Recent transactions (the placeholder comment in
  `components/dashboard/home-dashboard.tsx`).
- **"Insights"**, the generated time, **View all** → `/insights`, and the **top three stored
  insights by severity**: severity, section tag, summary.
- **Stale** (§4): a note — "You've added or changed transactions since these were written" — a
  **Refresh insights** link to `/insights` (which regenerates on arrival), and the old cards
  dimmed.
- **No set yet, but transactions exist:** an invitation to open Insights.
- **No transactions:** the home page already shows its own empty state; the callout is not
  rendered.
- **It never generates.** It only reads.

## 4. Freshness

- **Stale** means the user's transactions changed after `generated_at`: any row **added,
  edited, recategorised, re-flagged recurring, or soft-deleted**. Legacy looked at
  `created_at` only and missed every edit and delete.
- Detection: the latest `updated_at` over **all** the user's transaction rows, soft-deleted
  included, compared with `generated_at`. This needs a read method on `transaction` (allowed by
  the brief). The builder must confirm that every write path, including the bulk
  `update()`/soft-delete statements in the repository, moves `updated_at`; a path that does not
  is fixed in `transaction` in this step.
- **"Delete all transactions" deletes the stored set too.** The set holds merchant names and
  amounts taken from the deleted rows, and `docs/data-model/transaction.md` D4 hard-deletes on
  delete-all because "a row that holds a person's finances is not kept once they ask for it to
  go". Keeping the set — and showing it dimmed after a re-import — would contradict that.
  - Mechanism: `transaction` publishes an event when delete-all runs (from the Settings route,
    not from erasure, which `USER_ERASING` already covers), and `insights` subscribes inline and
    deletes the user's row. R6 forbids `transaction` importing `insights`, so an event is the
    only shape.
  - Publishing that event is a write-path change in `transaction`, outside the brief's "a read
    method", so it goes to the coordinator for approval before the plan runs.
  - `transaction.md` D4 gains a line naming the event; `insight.md` records the subscriber.
- As a backstop, "no transactions" still wins over any stored set: `GET` answers `no_data` and
  shows no cards.
- **Opening `/insights` when there is no set or it is stale generates.** Opening it when fresh
  costs nothing, however often.
- **Regenerate always generates**, stale or not: the model may give a different reading of the
  same figures, and the user asked for it.

## 5. What the model is given and what it returns

### 5.1 The period: this month against your usual

- **This month** is the dashboard's **`reference_month`**, by analytics-figures' rule (user's
  decision, 16 Oct 2026): every analytics period is made of **finished** calendar months,
  anchored at the latest finished month with data. Insights and the dashboard therefore talk
  about the same month.
- **And the month so far** (the user, 16 Oct 2026). When the current month has data, the model
  also gets the month to date — the dashboard's `month_to_date` (income and expenses through
  `through`, against the same days of the previous month), plus spend by category over the same
  two spans (the ranged calls take `date_from`/`date_to`). It may add **one or two** insights
  about how the month is going, marked `period: "month_to_date"` (§5.3). A weekly uploader
  therefore gets something new mid-month, not only a "refresh" note.
  - These are the only insights about a partial month, and they compare like with like (same
    days), never a partial total against a full month.
  - Their severity is capped at `medium`: half a month is a hint, not a verdict.
  - With no current-month data there are none, and the set is about the finished month alone.
- **Your usual** is up to the **six finished months before** it that hold data (fewer for a new
  user; none for a user with one month, who gets observations about this month alone). The
  ranged analytics calls take `months` (1–120) for this.
- **Partial only as a fallback.** When no finished month has data (a new user in their first
  month), analytics falls back to the current month and says so (`reference_partial`). Then the
  model is told the month is in progress and through which day, and the prompt forbids reading a
  partial month's lower total as a fall in spending.

### 5.2 The figures

From `analytics_service`, read-only (condition 2: no edit to `app/modules/analytics/`):
spending (the reference month and the baseline window, with its monthly series), categories,
merchants, recurring, behaviour, and anomalies — over the windows above. Which call covers
which window is the builder's, provided the model sees, for this month and for the usual:
total spend and income, savings rate, spend by category and which categories grew or fell, top
merchants and concentration, recurring cost and subscriptions (incl. hidden ones),
weekend/weekday per-day spend, category stability, outliers and category spikes.

**Only aggregates go to the model**, never transaction rows. Merchant names in the figures
(top merchants, recurring merchants, outliers) are allowed — they are what makes a card
specific. Amounts are passed as plain decimals in EUR.

If the gap between what the model needs and what `analytics_service` returns turns out to need
a change in `analytics`, it goes to the coordinator (`orchestrator`) before any edit.

**The analytics interface is changing under this step** (coordinator, 16 Oct 2026). A new step,
`analytics-figures` (branch `feat/analytics-figures`), owns `app/modules/analytics/` and merges
into `template-base` before 6. Every `analytics_service` function keeps its name and arguments;
some result shapes change, and its PR lists them. This design is written against the corrected
semantics, not today's:

- **Category growth** (`top_growing` / `top_declining`) compares the average monthly spend of the
  range's earlier half with its later half, ranked by the change in €, and includes categories
  that fell to zero (−100%) and new ones. Today's first-month-versus-last-month figure is not
  used.
- **New derived figures** the model should get where they exist: the savings rate per month and
  for the period (the natural input for the Savings section), a 3-month rolling average of
  expenses, and weekday spend averaged per occurrence.

analytics-figures is also reviewing the whole module for correctness, so **any result field may
change shape**; it lists every changed field before its PR opens, and the coordinator forwards
the list. Hence:

- **One place reads analytics shapes**: a single function in `app/modules/insights/` that calls
  `analytics_service` and builds the model's input as plain values. Nothing else in the step —
  not the agent, the prompt's structure, the stored set or the web — names an analytics field.
- The corrected meanings expected (coordinator, 16 Oct 2026): recurring monthly cost handles
  annual charges and cancelled merchants; a new hidden-subscription rule; stability no longer
  counts single purchases; outliers stop flagging rent every month; spikes get a floor and a
  better ranking; possibly new merchant risk bands; partial months, zero-filled ranges and
  future-dated rows handled; rounding half-to-even. The prompt is written for those meanings.
  **No prompt wording, severity guidance or threshold is tuned against today's output**; the
  prompt is checked against real figures only after the merge.
- **The final fields** (analytics-figures' approved spec, §3–4, read-only at
  `.claude/worktrees/analytics-figures/.superpowers/specs/2026-10-16-analytics-figures-design.md`):
  every response echoes `date_from`/`date_to`; dashboard gains `reference_partial` and
  `month_to_date`; recurring gains `interval_days`, `last_charge`, `active`, with `monthly_cost`
  and `monthly_recurring_cost` redefined; stability's CV is over monthly totals and gains
  `months`; outliers are within each category, recurring excluded; spikes gain
  `increase_amount`, ranked by €, and a null window means "not checked"; merchants'
  `concentration.risk` is removed (the model gets the index and shares, and judges);
  category growth items are `{category, earlier_monthly_average, later_monthly_average,
  change_amount, change_pct}`, each category gains `previous_total` and `change_pct`; spending
  gains `savings_rate_pct`, `average_monthly_net` and `latest_month`. Late changes:
  `month_to_date`'s `income_change_pct` / `expenses_change_pct` are null when the previous month
  is only partly in the data (the model is then given no comparison and must not invent one);
  hidden subscriptions are "never flagged, monthly, steady, ≤ €50"; `weekend_bias_pct` is null
  without weekend days. **The authority is PR #16's description (`gh pr view 16`)**, which lists
  every changed field with its old and new meaning; this list is a pointer.
- **Merged.** analytics-figures landed in `template-base` as `47db8eb` and this branch
  fast-forwarded to it on 16 Oct 2026, so nothing in this step waits any more. The
  single-reader rule above still holds.

### 5.3 The answer

One model call returns a list of **usually 4 to 8 insights** (the model chooses how many; more
than 10 is invalid). **Zero is a valid answer** — a sparse first month may honestly have
nothing worth saying, and forcing a card invites filler. A zero-card set is stored like any
other (`fresh`, `generated_at` set) and shown as "Nothing stands out this month" on the page and
in the callout, so it does not regenerate on every visit. Each insight:

| Field | What it is |
|---|---|
| `section` | `spending` · `recurring` · `savings` · `anomalies` · `comparisons` — decides the tab |
| `period` | `month` (the finished reference month against the usual) or `month_to_date` (§5.1); a `month_to_date` card shows a small "October so far" tag, and the server caps its severity at `medium` |
| `severity` | `info` · `low` · `medium` · `high` · `critical` |
| `summary` | one sentence; the card title |
| `narrative` | one to three sentences; what it means, and one concrete step where there is one |
| `key_figure` | optional, structured: `{kind: "amount" \| "percent" \| "count", value: <number>, qualifier: <short text, e.g. "/ month", "vs usual">}` |
| `link` | optional: `{kind: "recurring"}`, `{kind: "category", category: <slug>}`, or `{kind: "merchant", merchant: <name>}` |

- **The chip is formatted by the web**: an amount through the app's existing EUR formatter (the
  browser's locale, like every amount in the app), a percent with its sign, a count as is, then
  the qualifier. The model never formats the chip's number.
- **Amounts in `summary` and `narrative`** are prose the model writes, so they cannot follow the
  browser's locale. The prompt fixes one form: `€` before the number, whole euros with a comma
  for thousands (`€1,240`), cents only under €10 (`€4.99`).

- **Links are validated on the server**: a category must be a real slug, a merchant must appear
  in the figures the model was given; an invalid link is dropped, not the card. The web builds
  the URL against `/transactions`' existing query params (`is_recurring=true`;
  `category=<slug>`; `search=<merchant>`), scoped to the reference month with
  `date_from`/`date_to` for category and merchant.
- Legacy's `type`, `time_window` and `confidence` fields are **dropped**: `section` carries the
  grouping, the period is the set's (stored once), and a model's self-rated confidence told the
  user nothing. `insights.md` §3 is rewritten accordingly.
- **No invented figures** is enforced by the prompt (every amount and percentage must come from
  the figures, rounded as given) and by the data shape (aggregates only). A mechanical check of
  numbers in the text is **not** required; the builder may add a cheap one if it proves easy.
- The prompt lives under `app/agents/insights/prompts/`, versioned like the labeller's
  (`PROMPT_VERSION`), and the version is stored with the set.

### 5.4 The call

- Under `app/agents/insights/`, on the labeller's pattern: plain values in, a validated
  structured answer out, through `structured_llm_service` and `ask_json` (one retry on an
  invalid answer). Not `llm_service`; not in `AGENT_REGISTRY`; no LangGraph graph — it is one
  call. `app.agents` imports no module (R2), so `insights` builds the plain input and passes it
  in.
- Traced with `create_trace_config`, named `insights`, grouped by a per-generation id.
- **A failed call** (model error, or still invalid after the retry) leaves the stored set
  untouched and returns an error the web shows by the button. Nothing partial is stored.

## 6. Server

### 6.1 Module

A new `app/modules/insights/` on the existing module pattern (the `server-patterns` skill), with
everything the brief lists for registration: `main.py` import line, `api/v1/api.py`,
`alembic/env.py`, its R1 contract plus `app.modules.insights.*` in the four existing R1
contracts, and R6 as `"app.modules.conversation | app.modules.insights"` above
`app.modules.analytics`. It calls `analytics_service` and `transaction`'s public API only.

### 6.2 Storage

One table, the wave's only migration: **one row per user**, replaced on each generation.

- `user_id` (owned table, unique — one set per user), `generated_at`, `reference_month`, the
  baseline months used, the month-to-date span if any (month and `through`), `prompt_version`,
  and the insights as a JSON array in the shape of §5.3.
- Storing the set as one JSON document (not a row per insight) is deliberate: the set is always
  read and replaced whole, and its shape follows the prompt.
- A `USER_ERASING` subscriber deletes the user's row (inline, like `transaction`'s), and a
  subscriber to `transaction`'s delete-all event does the same (§4).
- `docs/data-model/insight.md` is written in this step (the data-model link in `insights.md`
  is "pending — written with step 6").

### 6.3 Routes

Two routes under `/api/v1/insights`:

- **`GET`** — the stored set and its state, **never generating**: `status` (`no_data` — no
  active transactions; `none` — transactions but no set; `stale`; `fresh`), `generated_at`,
  `reference_month`, and the insights. The callout and the page both read it.
- **`POST /generate`** — generates now, stores, returns the same shape (`fresh`). With no
  transactions it does not call the model and returns `no_data`. The page calls it on arrival
  when `GET` says `none` or `stale`, and on Regenerate.

Separating the read from the generation is what keeps the home page from ever triggering a model
call (§3.2) — legacy's single `GET` generated as a side effect.

Two generations at once (two tabs) may both call the model; the later write wins. Acceptable for
one user; no lock is required.

### 6.4 Limits

- `POST /generate` carries the app's ordinary per-user rate limit, as legacy's endpoint did
  (10 a minute), as a guard against runaway clicks — not as a product rule.
- No cooldown, no daily cap (the user, 16 Oct 2026). `TODO.md` gets: *a per-user cap on
  insight generation before public sign-up*.

## 7. Web

- `/insights` page, `components/insights/` (page, tabs, card, header with generated-at and
  Regenerate, empty and error states), the sidebar entry, and the home callout under
  `components/dashboard/` (condition 6: only step 6 edits that folder).
- Generated hooks only (`@app/api-client/endpoints/insights`); no hand-written API types.
- Generating invalidates the insights query; any transaction write already invalidates analytics
  (`use-invalidate-transactions`) and should invalidate the insights `GET` too, so the callout
  turns stale without a reload.
- Dates and amounts formatted with the app's existing formatters (EUR).
- The `web-app-patterns` and `web-app-testing` skills govern placement, loading states and
  tests.

## 7a. Home: month to date (scope added 16 Oct 2026)

By the user's decision, relayed by the coordinator: the dashboard's cards describe the last
finished month, and the month in progress is shown separately as **month to date**, compared
with the same days of the previous month. analytics-figures adds the server side; step 6 builds
the display, because it owns `components/dashboard/` this wave.

- Data: `/analytics/dashboard`'s `month_to_date` — `{month, through, income, expenses,
  previous_month, previous_income, previous_expenses, income_change_pct, expenses_change_pct}`,
  null when the current month has no data (then nothing is shown). `monthly_trend` may hold
  fewer than six points; the trend chart must cope.
- What it shows: "October so far", the days covered ("1–16 Oct · vs 1–16 Sep"), spent and income
  each with its change against the same days of last month, and net. The welcome header's
  "Your overview for <month>" names the finished month.
- Layout (the user's choice, 16 Oct 2026, mockup B): a **tall card on the left** — "October so
  far", the days covered, spent large with its change, income and net below, a "16 of 31 days"
  bar — and the **four cards two by two on the right**, in one row. On a phone the card stacks
  above the four. When `month_to_date` is null, the four cards take the full row as today.
- A change pct may be null (previous month only partly in the data): the card then shows the
  figure without a comparison.

## 8. Docs that change in the PR

- `docs/product/features/insights.md`: rewritten to this design (§3, §4 rules, §6 open questions
  answered: cooldown dropped, savings tracker not built, cap deferred to `TODO.md`).
- `docs/data-model/insight.md`: new.
- `docs/data-model/transaction.md` D4: the delete-all event.
- `docs/TODO.md`: the per-user cap.
- `docs/ROADMAP.md`: row 6 → `complete` with the PR link.
- This spec and the plan are deleted.

## 9. Left to the builder

- How the analytics calls map to the windows in §5.1–5.2, and the exact JSON handed to the model.
- The prompt's wording, within §5.3 and the anti-goals.
- Column types, index names, the response schema names.
- Component breakdown under `components/insights/`, copy for empty and error states.
- Whether to add a cheap numeric check (§5.3).
