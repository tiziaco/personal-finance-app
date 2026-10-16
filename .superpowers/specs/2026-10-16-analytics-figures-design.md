# Analytics figures — design

**Step:** `docs/ROADMAP.md` row *Analytics figures* · **Branch:** `feat/analytics-figures` → PR into `template-base`
**Owns:** `server/app/modules/analytics/` and the contract change it makes (`make gen-contract`). Nothing under
`web-app/apps/web/`, no other server module, no migration.
**Read with:** [`docs/product/features/analytics.md`](../../docs/product/features/analytics.md) (§3 is the
calculation contract this spec amends).

## 1. Why

Wave 3 builds three things on the analytics module: the `/analytics` page (5b), insights (6) and the chat's
finance tools (7). Insights and chat repeat these numbers to the user as fact, so a misleading figure is worse
than a missing one. A read-only review of the whole module (16 Oct 2026) found that most figures compute what
the doc says, but:

- **periods do not match the data** — a partly imported month counts as a whole one, a range running past or
  before the data zero-fills, a future-dated row stretches the default range, and a `DateRange` built in code
  (as 6 and 7 do) is never validated;
- **several measures mislead** — category growth (first vs last month with spend), recurring monthly cost,
  hidden subscriptions, stability, outliers, category spikes, the merchant "risk" band;
- **a few small defects** — rounding, the dashboard trend, descriptions.

The user decided to fix all of it in this step, together with every derived figure 5b's page needs, so the
page computes nothing. 5b, 6 and 7 wait for this merge on the fields that change.

**Success:** every figure on the four tabs and the dashboard comes from the server; each number means what a
person reading it would take it to mean; 6 and 7 get the same validation and period rules as the endpoints.

**Anti-goals:** arithmetic in the page; a number that is right by the code and wrong to the reader (the growth
bug's kind); a new endpoint per tab (the page reads the existing seven).

## 2. Decisions taken with the user

1. **Finished months, and month-to-date beside them** (user, 16 Oct 2026). Every period is made of finished
   calendar months. The month in progress is reported separately as month-to-date, compared with the same days
   of the previous month. This follows the industry convention (trailing periods use completed months; a partial
   period is shown as *-to-date*). It **reverses the 15 Oct 2026 dashboard decision** ("the latest month with
   data"): the dashboard's reference month becomes the latest *finished* month with data. Insights (6) builds
   the dashboard's month-to-date display (orchestrator ruling). When no finished month holds data yet, every
   view falls back to the month in progress, marked partial (user, 16 Oct 2026).
2. **Category growth** (user, with 5b): the earlier half of the period against the later half, by each half's
   average monthly spend, ranked by the change in €. Dropped to zero → −100; present only in the later half →
   `change_pct` null ("new").
3. **The measure fixes in §5** (user, 16 Oct 2026), as proposed.
4. **The Trends tab offers 4, 6, 12 and 24 months**; the server accepts any whole number (user).
5. **Every existing `analytics_service` function keeps its name and arguments** (brief; 6 and 7 plan against them).

## 3. Periods

### 3.1 Terms

- **Today** — `dt.datetime.now(UTC).date()`, read once in the service and passed into the domain as `today`
  (as `build_dashboard` already does), so tests pin it.
- **Current month** — today's calendar month. It is never finished.
- **Finished month** — any calendar month before the current month. (A past month whose import stopped early
  still counts as finished: the app cannot tell "nothing happened" from "not imported".)
- **Usable rows** — the user's active rows dated no later than the last day of the current month. A row after
  that is a typo or a scheduled entry; it is outside every period, including the dashboard's. (The doc's
  "if every row is in the future, the latest of them" rule goes.)
- **Data span** — first and last day of the usable rows.

### 3.2 How a request becomes a period

`DateRange` gains `months: Optional[int]` (1–120) and validates itself in a `model_validator`: each bound inside
`MIN_DATE`–`MAX_DATE`, `date_from ≤ date_to`, and `months` not combined with either bound. A violation raises
`InvalidDateRangeError` (422), so a `DateRange` built in code by 6 or 7 fails the same way the query string does.
`get_date_range` becomes a thin wrapper that reads the three query params and builds it.

One resolver (`domain/period.py`, new) turns `(DateRange, usable rows, today)` into a `Period`.

**The anchor month** is the latest finished month holding a usable row. **When no finished month holds one** —
a user whose only data is this month — the anchor falls back to the current month, which is then partial
(user, 16 Oct 2026: a new user sees their month in progress, marked as such, rather than empty views). The
dashboard's reference month is the same anchor.

- **`months=N`** — the N calendar months ending at the anchor, starting no earlier than the data's first month.
- **No bounds, no months** — from the data's first month to the anchor.
- **Explicit bounds** — the given days, clipped to the data's months: the start no earlier than day 1 of the
  data's first month, the end no later than the last day of the data's last month and never past the current
  month. An omitted bound takes that clip. A range inside the data's months that holds no rows (a gap between
  imports) is a zero-filled period, not an empty one.
- **Empty period** (`date_from`/`date_to` null, empty series, zeros, no error) only when the user has no usable
  rows, or the explicit range lies wholly outside the data's months.

**Days.** A period runs over whole calendar days: from day 1 of its first month to the last day of its last
month, except where a month is partial (below). Every day-based figure — the echo, `by_weekday[].days`,
weekday/weekend days, the spike window, recurring `active`, the previous period's length — uses these days.

**A month is partial for exactly three reasons**, and no other (a past month whose import stopped early is
whole):

1. an explicit bound cuts it — its days start at `date_from` or end at `date_to`;
2. it is the current month — its days end at the last usable row's day in it;
3. it is the data's first month and its first usable row falls after day 7 — its days start at that row's day.

Each month has a **weight**: 1 when whole, else its days ÷ the days in the month.

### 3.3 Rules every analysis follows

- **Monthly averages** are totals ÷ the sum of month weights, so whole months divide by N exactly and a partial
  month counts for the fraction of it covered.
- **Month-over-month change, seasonality, stability and the growth halves use whole months only.** A change
  touching a partial month is null.
- Every monthly series is zero-filled over the period and marks partial months.
- **Every response echoes the period** as `date_from`/`date_to` (null when empty). Spending already does;
  categories, merchants, recurring, behaviour and anomalies gain them.
- **Every ranged endpoint accepts `months`** (spending, categories, merchants, recurring, behaviour,
  anomalies). Giving it with `date_from`/`date_to` is a 422.

### 3.4 Rows the service loads

`months=N`, the previous period, the rolling average, a first month's change and the outlier windows all need
rows outside the period, and resolving `months` needs the data span. The service therefore loads all of the user's rows
(`MIN_DATE`–`MAX_DATE`, as the dashboard does today) and the domain filters. A single person's history is a few
thousand rows; this is the builder's to revisit if a profile shows otherwise.

## 4. Figures by endpoint

Money is a decimal string to the cent, rounded **half-up** (was half-to-even); a percent is 0–100 to 2 dp; a
figure with nothing to divide by is null. Field names below are final unless the builder finds a clash.

### 4.1 `GET /analytics/spending`

New and changed fields:

| Field | Meaning |
|---|---|
| `average_monthly_income`, `average_monthly_expenses` | **Changed:** totals ÷ month weights (§3.3). |
| `average_monthly_net` | **New.** Net ÷ month weights. |
| `burn_rate` | Unchanged formula; description now states the sign: expenses minus income per month, negative while saving. |
| `savings_rate_pct` | **New.** Period net ÷ income × 100; null when income is 0. |
| `months[].partial` | **New.** bool. |
| `months[].expense_change_pct` | **Changed:** null when this month or the month before is partial. The period's first month compares with the month before the period when usable rows exist there (else null). |
| `months[].expenses_rolling_avg_3m` | **New.** Mean of this month's and the two previous months' expenses, reaching before the period; null when any of the three is partial or before the data's first month. |
| `months[].savings_rate_pct` | **New.** Month net ÷ income × 100; null when income is 0. |
| `latest_month` | **New**, nullable. The last whole month of the period: `{month, income, expenses, income_vs_average_pct, expenses_vs_average_pct}`; each pct compares it with the period's monthly average (which includes it), null when that average is 0. |
| `month_to_date` | **New**, nullable. See §4.7. Independent of the period. |

### 4.2 `GET /analytics/categories`

- Response gains `date_from`, `date_to`, `previous_date_from`, `previous_date_to`. The **previous period** is
  the same length immediately before: N months for `months=N`, the same number of days for explicit bounds;
  null when no usable row falls in it.
- Each item of `top_categories` and `by_frequency` gains `previous_total` (that category's spend in the previous
  period; null when there is no previous period) and `change_pct` (null when `previous_total` is 0 or null).
  Categories present only in the previous period are not listed here.
- `top_growing` / `top_declining` are **reshaped** to items `{category, earlier_monthly_average,
  later_monthly_average, change_amount, change_pct}`:
  - the period's whole months split into an earlier and a later half; with an odd count the middle month is left
    out; fewer than 2 whole months → both lists empty;
  - each half's average is its spend ÷ its months; `change_amount` = later − earlier;
  - `change_pct` = change ÷ earlier × 100; −100 when the later half is zero; null when the earlier half is zero
    ("new");
  - growing = `change_amount` > 0, declining < 0; each ranked by |`change_amount`| (ties by slug), top 5.
  - The old `first_month_total`, `last_month_total`, `growth_pct` and `cv` go (variability lives in behaviour's
    stability).

### 4.3 `GET /analytics/merchants`

Gains `months` and the `date_from`/`date_to` echo. `concentration.risk` is **removed** (its bands are antitrust
thresholds; rent alone makes anyone "high"); `top_5_share_pct`, `top_10_share_pct`, `herfindahl_index` and
`unique_merchants` stay.

### 4.4 `GET /analytics/recurring`

Gains `months` and the echo. Per merchant (still keyed by the stored flag, grouped by merchant key):

- `interval_days` (**new**, nullable): the median gap in days between consecutive charges; null with one charge.
- `monthly_cost` (**changed**), by billing rhythm: with `interval_days` ≥ 25, median charge ÷ `cadence`, where
  `cadence` = max(1, round(`interval_days` ÷ 30.436875)) months (€10 every 28–31 days is €10.00; €600 every 365
  days is €50.00); below 25 days, median charge × 30.436875 ÷ `interval_days`; with one charge, the charge ÷ the
  period's month weights.
- `last_charge` (**new**) and `active` (**new**): active unless the period's last day is more than
  1.5 × `interval_days` after `last_charge`. A single charge is active.
- `monthly_recurring_cost` (**changed**) sums active merchants only.

`hidden_subscriptions` keeps its item shape, with a **new rule**: an unflagged merchant charged in at least 3
distinct months, with a median gap of 25–35 days, every charge within 10% of the median charge, and a median
charge of €50 or less. Ranked by median charge × charges per month, descending.

### 4.5 `GET /analytics/behaviour`

Gains `months` and the echo.

- `by_weekday[]` gains `days` (occurrences of that weekday in the period) and `per_day` (total ÷ days). `total`,
  `count`, `average` (per transaction) and `share_pct` stay.
- `weekend_bias_pct` (**fixed**): computed from unrounded per-day spend.
- `seasonality[]` (**changed**): built from whole months only. Each item gains `years` (how many whole months of
  that calendar month the period holds). `average_spend` is their mean; `index` is that ÷ the mean of all whole
  months × 100; null when `years` is 0 or the mean is 0. Shown with less than a year of data; `years` lets the
  page say so.
- `stability[]` (**changed**): the CV of each category's monthly totals over the whole months from its first
  month with spend; needs 3 such months. `count` stays the number of expenses; **new** `months` is the months
  judged. Thresholds unchanged (stable < 0.3, moderate < 0.7). The three `*_share_pct` follow.
- `expense_change_pct` (**changed**): between the period's last two *whole* months.

### 4.6 `GET /analytics/anomalies`

Gains `months` and the echo.

- **Outliers** (**changed**): recurring-flagged expenses are left out — as candidates and from every window — and
  each expense in the period is compared only with the earlier expenses of **its own category** in its
  `window_days` window (own day excluded, ≥ 5 expenses, nonzero spread). The window may reach before the
  period's start, so `months=1` still has history to compare with. `window_mean` is that category window's
  mean. Top 20 by z.
- **Spikes** (**changed**): the 30-day window ends at the period's last day and the baseline starts at its first
  — both already clipped to the data (§3.2), so empty days no longer dilute. Flagged above 50% *and* when the
  increase (recent − baseline) is at least 5% of the period's average monthly spend. Each item gains
  `increase_amount`; ranked by it, descending.
- `spike_window_start`/`end` are null when spikes were **not checked** (less than 30 days of baseline, or no
  data); an empty `spikes` with a window means "checked, none".

### 4.7 Month-to-date (spending and dashboard)

`month_to_date`, null when the current month holds no usable row:

`{month, through, income, expenses, previous_month, previous_income, previous_expenses, income_change_pct,
expenses_change_pct}` — the current month from day 1 to `through` (the last usable row's day in it), against
the previous month's days 1 to the same day number (clamped to that month's length). Each pct is null when its
previous figure is 0.

### 4.8 `GET /analytics/dashboard`

- `reference_month` (**changed**): the anchor month (§3.2) — the latest *finished* month holding a usable row,
  else the current month; null only with no usable rows, so the web empty state keeps working unchanged.
- `reference_partial` (**new**, bool): true when the reference month is the month in progress (the fallback).
- `monthly_trend` (**changed**): the six months to the reference month, but not before the data's first month —
  so it can hold fewer than six points.
- `average_cashflow` / `cashflow_months`: unchanged rule, over the months to the reference month.
- `month_to_date` (**new**), as §4.7. When `reference_partial` is true it repeats the reference month; the web
  can show either.

## 5. Small fixes

- `money()` rounds half-up.
- Schema descriptions match the code (the growth item, `MonthOfYear.index`, the spike window, `burn_rate`'s sign,
  per-transaction `average_income`/`average_expense`).

## 6. Contract and callers

- Run `make gen-contract`; commit `server/openapi.json` and the generated client.
- Removing or reshaping a field breaks any web file that reads it; the web dashboard reads only
  `reference_month`, `monthly_trend` and the cards' fields, which keep their types. `make check-web` must pass.
- **The PR description lists every changed field with its old and new meaning** (orchestrator's request, for 6's
  insights graph and 7's tools). Section 4's **Changed / New / removed** marks are that list's source.
- After the spec is approved, send the orchestrator the exact `month_to_date` and spending field names (§4.1,
  §4.7) for 5b and 6.

## 7. Testing

Unit tests per domain file, with `today` pinned; each review finding gets the test that would have caught it:
partial first and last months; a range past and before the data; a future-dated row; an annual and a cancelled
recurring merchant; a coffee burst and a varied grocer against a €9.99 monthly subscription; steady monthly
groceries made of varied purchases; monthly rent among daily spend; a €1 → €40 category; `DateRange` built in
code with bad bounds, reversed bounds, and `months` with a bound; half-cent rounding. Route tests cover `months`
on each endpoint, the 422 for `months` with a bound, and the echo. `make check-server` passes.

## 8. Docs, when the PR is opened

- `docs/product/features/analytics.md`: §2 (dashboard reference month and month-to-date; the page's periods),
  §3 (every amended rule here), §5 (the risk label is gone), §6 (savings rate answered; the 15 Oct dashboard
  decision marked reversed with the date and why).
- `docs/TODO.md` line on the dashboard month picker: reword "latest month with data" to "latest finished month".
- `docs/ROADMAP.md`: the row → `complete` with the PR link; a decision note for finished months.
- This spec and its plan are deleted.

## 9. Left to the builder

File layout inside the module beyond `domain/period.py`; how the resolver is threaded through each domain
function (keyword `period` alongside the existing optional `date_from`/`date_to` is fine, as long as each public
function keeps its current parameters); helper names; test fixtures.
