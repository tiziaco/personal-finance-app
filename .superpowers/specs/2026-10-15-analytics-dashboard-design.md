# Step 5a — Analytics dashboard: design

**Date:** 15 Oct 2026 · **Branch:** `feat/analytics-dashboard` → PR into `template-base`
**Reads:** [`docs/product/features/analytics.md`](../../docs/product/features/analytics.md),
[`docs/data-model/transaction.md`](../../docs/data-model/transaction.md), `.superpowers/BRIEF.md`
(ownership and the eleven conditions).

---

## 1. Outcome

The whole analytics computation library, its routes, and the home dashboard. Steps 5b
(analytics page), 6 (insights) and 7 (chat tools) build on the library without changing it:
5b is web-only because every analysis has a route here; 6 and 7 call `analytics_service` in
Python.

**Decided before this spec (the user, 15 Oct 2026), not reopened:** recurring reads the
stored `is_recurring` flag only — no detection here; money is EUR only (`format.ts`
unchanged); the empty state links to `/transactions`; `analytics` is not placed above
`conversation` in R6.

**Decided in brainstorming (15 Oct 2026):**

- **D1 — the dashboard's period is the latest month with data** (the *reference month*):
  the latest calendar month holding an active transaction, labelled by name ("September
  2026"). v1.0 showed the same month but labelled it "this month". Rejected: the current
  calendar month (imports lag the calendar, so the dashboard would often read zero); a
  month picker (later, see §9 — every route already takes a range).
- **D2 — Recurring Costs is the flagged spend paid in the reference month**, with
  "N recurring payments" under it. Rejected: v1.0's month expense × all-time recurring
  share (mixes two periods); a run-rate on the card (an estimate, unstable for a merchant
  with one or two charges). The run-rate exists as the library's *monthly recurring cost*.
- **D3 — plain Python, no dataframe library.** The library is pure functions over plain
  rows using `statistics` and one helper file. No polars, no numpy (numpy is only a
  transitive dependency today). Rejected: polars (large binary, float money, a specifier to
  coordinate with step 4, DataFrames leaking into 6 and 7's interface); SQL aggregates
  (the library would live in `transaction`'s repository, rolling statistics are awkward in
  SQL, nothing testable without Postgres). A future free-form chat over the user's data
  runs generated code in a sandbox with its own environment; the server only hands it rows,
  so polars still does not enter `server/pyproject.toml` (§9).

## 2. Server — transaction's read path

The only change inside `server/app/modules/transaction/` (conditions 1 and 2): additions to
`schemas.py`, `repository.py`, `service.py`, `__init__.py` and their tests. No column, no
index, no migration, no edit to `models.py`.

- `schemas.py`: `AnalysisRow`, a frozen Pydantic model — `date: dt.date`,
  `merchant: str`, `amount: Decimal`, `category: str`, `is_recurring: bool`.
- `repository.py`: `list_active_rows_for_analysis(session, user_id, date_from, date_to)`
  selects those five columns for the user's active rows (`deleted_at IS NULL`), optional
  inclusive date bounds, ordered by `date, created_at, id`. Served by
  `ix_transaction_user_id_date`.
- `service.py`: `transaction_service.list_for_analysis(session, user_id, date_from=None,
  date_to=None) -> list[AnalysisRow]`.
- `__init__.py`: exports `AnalysisRow`.

## 3. Server — the `analytics` module

Stores nothing: no table, no Alembic revision.

```
app/modules/analytics/
  __init__.py      # public surface: router, analytics_service, response schemas
  router.py        # GET /analytics/... (§4)
  schemas.py       # response models
  service.py       # rows via transaction_service → domain → schemas
  domain/          # pure functions; imports no ORM, no framework, no other module (R9)
    __init__.py
    _aggregate.py  # Row Protocol, group_by, month helpers, zero-filled month range,
                   #   trailing window, safe pct_change, share
    spending.py    # per-month income/expense/net, totals, averages, burn rate
    categories.py  # ranked spend + share, frequency vs impact, per-category growth and CV
    merchants.py   # top by spend and by frequency, top-5/top-10 share, Herfindahl, risk
    recurring.py   # flagged spend and share, monthly recurring cost, hidden-subscription candidates
    behaviour.py   # day of week, weekday vs weekend, seasonality, stability classes, MoM expense change
    anomalies.py   # trailing z-score outliers, recent category spikes
    dashboard.py   # the home figures for the reference month
```

`domain/_aggregate.py` declares a `Row` `Protocol` (the five fields), so `domain` never
imports `transaction`; `service.py` passes `AnalysisRow`s, which satisfy it. Domain
functions return frozen dataclasses; `service.py` maps them to the Pydantic response
models in `schemas.py`.

### 3.1 Rules every function follows

- **The sign decides.** `amount < 0` is an expense, measured as `abs(amount)`;
  `amount > 0` is income; `amount == 0` is ignored by every sum, count and average.
  No category is treated specially (Income, Salary and Savings count by sign only).
- **Months are zero-filled.** A per-month series covers every calendar month from the
  first to the last month of the range — the given bounds, or the data's first and last
  dates when a bound is omitted — with zeros for months without transactions. Averages
  "per month" divide by that month count.
- **Money stays `Decimal`,** quantised to cents, and is serialised as a string, like
  `amount` today. Ratios, shares and scores are `float`; **every percent is 0–100**.
- **Never divide by zero.** Empty input gives zeros, `null` for an undefined ratio (e.g.
  growth from a zero month), and empty lists. Nothing raises.

### 3.2 What each analysis computes

Defaults in brackets. "Range" is the optional inclusive `date_from`/`date_to`.

- **spending** — per month: income, expenses, net (income − expenses), expense
  month-over-month change (percent, `null` after a zero month). Totals for the range:
  income, expenses, net, transaction count, average income and expense per transaction.
  Average monthly income and expenses, and burn rate (average expenses − average income).
- **categories** [`top_n` 10] — expenses grouped by category: total, count, average,
  share of all expenses; ranked by total, cut to `top_n`. Frequency vs impact: the same
  groups ranked by count. Per category with ≥ 2 months of data: growth (first to last month
  with spend, percent) and CV of its monthly totals; top growing and top declining
  (5 each).
- **merchants** [`top_n` 15] — expenses grouped by merchant (stripped, casefolded for
  grouping; displayed as the most recent spelling): total, count, average, first and last
  date; ranked by total and by count. Concentration: top-5 and top-10 merchants' share of
  **all** expenses; Herfindahl index = Σ(share %)² over all merchants (0–10000); risk
  `high` > 2500, `medium` > 1500, else `low`; unique merchant count.
- **recurring** — flagged expenses: total, count, share of all expenses (amount and
  count). **Monthly recurring cost:** per merchant with flagged expenses, median flagged
  charge × (flagged charges ÷ months in which it charged), listed per merchant and summed.
  **Hidden-subscription candidates:** merchants among *unflagged* expenses with
  average charge ≤ 50.00 and ≥ 3 charges per active month, ranked by frequency.
- **behaviour** — expenses by weekday (Mon–Sun): total, count, average, share.
  Weekday vs weekend: average spend per day, dividing by the number of such calendar days
  in the range; weekend bias percent = (weekend ÷ weekday − 1) × 100. Seasonality per
  calendar month: average spend across the years present, and an index against the mean
  monthly spend (100 = average). Stability per category with ≥ 5 expenses: CV of its
  transaction amounts; `stable` < 0.3, `moderate` < 0.7, else `volatile`; each class's
  share of classified spend. Month-over-month expense change between the last two months
  (named as such — v1.0 called it "subscription creep").
- **anomalies** [`std_threshold` 2.5, `window_days` 30] — **outliers:** each expense
  against the mean and standard deviation of the individual expenses in the preceding
  `window_days` days (excluding its own day); z = (amount − mean) ÷ stdev; flagged when
  z > threshold; skipped when the window holds < 5 expenses or stdev is 0; top 20 by z.
  **Category spikes:** expenses in the last 30 days of the range (counted back from its end
  date, or from the latest transaction when no end is given) per category, against that
  category's average 30-day spend over the rest of the range; flagged above +50 %.
- **dashboard** — §4.1.

v1.0 bugs this replaces, for the record: a Herfindahl index computed over top-N shares
(could exceed 10000); "monthly recurring cost" that was the average charge; a spike
baseline that was a per-transaction mean; a z-score of one transaction against a day's
total; weekday/weekend averages divided by 5 and 2; month-over-month change as a percent in
one field and a fraction in another.

### 3.3 Import-linter

- **R1:** a new contract for `analytics`, and `app.modules.analytics.*` added to each
  existing module's forbidden list; `tests/unit/test_module_contracts.py` stays green.
- **R6:** `analytics` imports `transaction`, so it sits above it, as an independent
  sibling of `conversation`: the layers become
  `"app.modules.conversation | app.modules.analytics"`, `"app.modules.transaction"`,
  `"app.modules.account"`. Not above `conversation`, so step 7 may place `conversation`
  above `analytics`.
- **R9:** the first `domain` slot, so the contract lands here, with both source patterns
  the orchestrator relayed from step 4: `app.modules.*.domain` and
  `app.modules.*.*.domain` may not import `sqlmodel`, `sqlalchemy` or `fastapi`. The
  `docs/TODO.md` R9 entry is left to step 4; at merge, step 4's block wins (condition 9).

## 4. Server — routes

Under `/api/v1/analytics`, registered in `app/api/v1/api.py`. Each takes `CurrentUser` and
`settings.rate_limits.endpoints.TRANSACTIONS[0]`. No envelope: the response model is the
body. Range params `date_from`, `date_to` (`YYYY-MM-DD`, inclusive, optional; omitted =
all time); `date_from > date_to` → 422.

| Route | Params | Consumer |
|---|---|---|
| `GET /dashboard` | — | home (5a) |
| `GET /spending` | range | 5b Income vs Expenses, Trends; 6; 7 |
| `GET /categories` | range, `top_n` 1–50 (10) | 5b By Category |
| `GET /merchants` | range, `top_n` 1–50 (15) | 6; 7 |
| `GET /recurring` | range | 6; 7 |
| `GET /behaviour` | range | 5b Seasonality; 6 |
| `GET /anomalies` | range, `std_threshold` 1.0–5.0 (2.5), `window_days` 7–90 (30) | 6; 7 |

### 4.1 `GET /dashboard`

Everything the home page draws; the web computes nothing.

| Field | Meaning |
|---|---|
| `reference_month` | `"YYYY-MM"`, the latest month with an active transaction; `null` with none |
| `total_spent` | expenses in the reference month |
| `recurring_spent`, `recurring_count` | flagged expenses in the reference month, and how many |
| `net_balance` | income − expenses in the reference month |
| `average_cashflow`, `cashflow_months` | mean monthly net over the up-to-3 months ending at the reference month, zero-filled, not before the user's first month with data; `cashflow_months` ∈ 1..3 |
| `spending_by_category` | the reference month's top 5 categories `{category, amount, share}` plus one `{category: null, …}` "other" entry when more exist; amounts sum to `total_spent` |
| `monthly_trend` | the 6 months ending at the reference month, zero-filled: `{month, income, expenses}` |

With `reference_month: null` the money fields are `"0.00"`, `cashflow_months` is 0 and the
lists are empty.

The recent transactions come from the existing `GET /transactions?limit=10`.

`make gen-contract` after the routes; `openapi.json` and the generated client are committed.

## 5. Web — the home dashboard

`(dashboard)/home/page.tsx` composes new components in `apps/web/src/components/dashboard/`,
client components on the generated query hooks, as `/transactions` does.

- **`welcome-header`** — "Welcome back, {first name}" (Clerk); subtitle "Your overview for
  September 2026", or "Your overview" with no data.
- **`summary-cards`** — four cards, a 4-column grid, 2 × 2 on mobile:
  Total Spent (subtitle: the month); Recurring Costs ("N recurring payments");
  Net Balance (destructive colour and a down-trend icon when negative);
  Average Cashflow ("average of N months"; destructive colour when negative).
- **`category-chart`** — donut of `spending_by_category`, labels from `use-categories.ts`,
  "Other" for the null entry; amount and share in tooltip and legend.
- **`trend-chart`** — income and expense lines over `monthly_trend`.
- **`recent-transactions`** — the 10 most recent: merchant, date, category, signed amount;
  "View all" to `/transactions`; a table on desktop, a card list on mobile.
- **Empty state** (`reference_month` null) — the header and one panel: "No transactions
  yet. Add or import transactions to see your overview", linking to `/transactions`.
- **Insights row** — a full-width row below the charts, left empty for step 6.
- `format.ts` and `use-categories.ts` are imported unchanged.

**Loading and errors.** A skeleton per section and `home/loading.tsx`. The dashboard query
and the recent-transactions query fail independently: the failed section shows
"Couldn't load …" with Retry (`meta: { silentError: true }`, no toast); the rest renders.

**Caching and refetching.** Analytics queries use `staleTime` 2 minutes.
`use-invalidate-transactions.ts` also invalidates every query whose key's first element
starts with `/api/v1/analytics/` (generated keys are `[url, params]`, so a prefix key
would not match). Every transaction mutation, and step 4's import (condition 4), goes
through it.

**The chart primitive.** `packages/ui/src/primitives/chart.tsx`, a new file imported by
subpath: shadcn's chart (container, tooltip, legend), added by hand per `web-app-patterns`
`references/components.md`. **New dependency:** `recharts` `^3.10.1` in `@app/ui`
(released 25 Jul 2026); the specifier goes to `orchestrator` (condition 8).

**Colours.** `--chart-1…5` in `packages/ui/src/styles/globals.css` are five near-identical
greys used nowhere. They get a validated categorical palette, light and dark, chosen with
the `dataviz` skill, plus `--chart-6` for "Other". Income and expenses keep one fixed pair of
colours wherever they appear.

## 6. Ownership check

Touched: `app/modules/analytics/**`; `transaction/{schemas,repository,service,__init__}.py`
and tests; `app/api/v1/api.py`; `app/main.py` (its module import, checked by `test_module_contracts`);
`server/pyproject.toml` (contracts); `server/openapi.json` and the generated client;
`(dashboard)/home/**`; `components/dashboard/**`; `packages/ui/src/primitives/chart.tsx`;
`packages/ui/src/styles/globals.css` (chart tokens); `packages/ui/package.json`;
`pnpm-lock.yaml`; `use-invalidate-transactions.ts`; docs per §8.

Not touched: `transaction/models.py`, `alembic/versions/`, `hub-nav.ts`,
`(dashboard)/layout.tsx`, `/transactions`, other `components/transactions/` files,
`packages/ui/src/index.ts`, existing primitives, hand-written `api-client` files,
`data-table`, `components`, `messages.ts`, `docs/data-model/transaction.md`,
`docs/data-model/README.md` §1, `docs/architecture/server.md` §2 and §8.

## 7. Testing

**Server** (`server-testing` skill):

- Unit, per `domain/` file, fixtures with hand-computed expectations: empty input, income
  only, a single month, gap months zero-filled, zero amounts, growth after a zero month
  (`null`), `Decimal` exactness, the trailing window's edges and minimum size, Herfindahl
  within 0–10000, hidden candidates excluding flagged rows, the 3-month average not
  reaching before the first data month, "other" making the category amounts sum to
  `total_spent`.
- Integration, transaction's read path: user-scoped, deleted rows excluded, inclusive
  bounds.
- Integration, each route: 401 signed out; 200 for a user with no transactions (dashboard
  `reference_month` null); another user's rows never count; 422 for an inverted range; one
  end-to-end dashboard check against seeded rows.
- `test_module_contracts`, `test_openapi_contract` and `lint-imports` green.

**Web** (Vitest): summary cards' subtitles and negative styling; the empty state's link;
a failed section shows Retry while the others render; the top-5 + Other mapping and its
labels; `use-invalidate-transactions` invalidates analytics queries and the list. Chart
SVG is not tested (jsdom cannot lay it out).

## 8. Docs, in the PR

- `docs/product/features/analytics.md`: "Data model: pending" → none, it reads
  `transaction`; §2 states the reference month and what each card measures; §6's
  dashboard-date-range question answered.
- `docs/architecture/server.md` §1: `analytics` in the module tree. Not §2.
- `docs/TODO.md`: the currency-symbol setting (`analytics.md` §4); a month picker on the
  dashboard; a sandbox for free-form chat queries over the user's rows (D3).
- `docs/ROADMAP.md` row 5a: `complete — [PR #N](url) into template-base; reaches main at
  Cutover`.
- This spec and the plan are deleted in the same PR.

## 9. Out of scope

The insights callout (step 6); the `/analytics` page (5b); chat tools (7); a dashboard
month picker; a currency setting; recurring detection (step 4); any free-form query
sandbox.
