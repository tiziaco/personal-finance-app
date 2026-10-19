# Analytics rules — design

Roadmap row **Analytics rules** (`docs/ROADMAP.md`). Branch `feat/analytics-rules`, PR into
`template-base`. Built beside **Wave 3 cleanup** (`feat/wave3-cleanup`) under the conditions in
`.superpowers/BRIEF.md` §3.

## Why

Step 6's insights run on synthetic data showed the analytics library reporting things a user
would call wrong: a €1,249 laptop missing from the unusual expenses, Lidl's weekly shop counted
as a recurring cost, an annual subscription not recognised until its third year, and a merchant
the user had said is not recurring suggested as a hidden subscription. Step 7's chat tools will
repeat whatever the library says, so the rules are fixed first. A typo year on a hand-added
transaction also drops it out of every chart without a word; the import already refuses one.

Success: each of the five cases below comes out the way a user would expect, proven by a test
that failed before the change, and the docs describe the rules as built.

## Goals

1. **Outliers in a thin category.** A large one-off purchase in a category the user rarely
   spends in is flagged (BUGS: *A large one-off purchase in a sparse category…*).
2. **Frequent shopping is not recurring.** A merchant visited about weekly with varying baskets
   is not flagged recurring (BUGS: *Frequent shopping at one merchant…*).
3. **Yearly charges.** Two same-amount charges a year apart are recurring (TODO: *a yearly
   charge is recurring only after three years*).
4. **Hidden subscriptions respect the user.** A merchant the user has unticked is never
   suggested (TODO: *a merchant the user unflagged…*).
5. **Date bounds on hand-entered transactions** (TODO: *a transaction added by hand is not held
   to the date bounds*).

## Non-goals

- No change to monthly or quarterly recurring detection.
- No change to the outlier measure in a category with enough history, to the threshold (2.5),
  the window (30 days), the top-20 cap, or category spikes.
- No backfill of stored `is_recurring` flags (decided: only dev and synthetic data exist; real
  data arrives after Cutover through imports, which run the rule). To see the new rules on dev
  data: delete all and re-seed or re-import (the seed change in rule 6 makes re-seeding enough).
- Nothing in `analytics/service.py`, `analytics/domain/spending.py`, `MonthToDateResponse`,
  `insights/` (including `insights/figures.py`) or `server/tests/conftest.py` — those belong
  to the cleanup (BRIEF conditions 1 and 4).
- No hand edits to `server/openapi.json` or the generated client; `make gen-contract` after the
  second of the two branches merges (condition 5).

## Anti-goals

- An outlier list that fills with ordinary purchases because a category is new or a month was
  quiet.
- Unflagging real bills: an electricity or phone bill that varies month to month stays
  recurring; a subscription whose price rose stays recurring.
- Overriding the user: a `recurring_source = user` row is never changed by the rule (unchanged
  from D6).

## The rules, as decided

### 1. Outliers — fall back to all one-off spending (`analytics/domain/anomalies.py`)

- Unchanged: each expense in the period is scored against the earlier one-off expenses of its
  **own category** in the `window_days` days before its day (own day excluded) when that window
  holds at least `MIN_WINDOW_EXPENSES` (5) of them.
- New: when the category's window holds **fewer than 5**, the expense is scored against **all
  the user's one-off expenses** (every category) in the same window, own day excluded, with the
  same z-score and the same `std_threshold`. It still needs at least 5 rows there and a nonzero
  spread; otherwise it is not scored.
- Two guards apply **to the fallback only** (decided after a simulation on the seed showed the
  bare fallback flagging €61–€105 cash withdrawals, a €192 savings transfer, IKEA €89 and
  Playtomic €49, because everyday one-off spending is mostly €10–€30):
  - **`atm` and `savings_investments` are never fallback candidates** — money moved, not spent.
    They still sit in the all-spending window, and they are still scored within their own
    category when it is dense, as today.
  - **The expense must be at least 5 % of the period's average monthly spend** — the same floor
    and the same base as category spikes (`SPIKE_MIN_SHARE_OF_MONTH` × the period's total
    expenses ÷ `period.weight()`); reuse it rather than a second constant. On the seed that is
    about €100, keeping Trip.com €1,501, Amazon €227 and TICKET.IO €117.
- Recurring-flagged expenses stay out, as candidates and from every window, in both cases.
- The measure stays the z-score (the bug asked to settle it): the fallback window always has
  plenty of rows, so one earlier large purchase does not dominate the spread; a median-based
  measure would change every dense category's results, which nobody has asked for.
- Rejected: flagging an expense that is a large share of the period's spend — in a quiet month
  it flags ordinary purchases.
- **Each outlier says what it was compared with:** a new field on `Outlier` and
  `OutlierResponse` (`analytics/schemas.py`), `compared_with: "category" | "all"`. `window_mean`
  is the mean of whichever window was used; its description changes to say so. Insights reads
  outliers but is not edited here; wording an insight from `compared_with` is a follow-up for
  whoever next touches insights (add a TODO entry).
- Ordering of the combined list stays by z-score descending, then date, category, merchant.

### 2. Weekly cadence — a fixed amount (`transaction/domain/recurring.py`)

- `weekly` needs **at least 4 rows** (was 3).
- Every row of a weekly series is within **2 % of the cluster's seed, with at least €0.10 of
  slack** (the user's line: "same amount every week"). Not €0.50: on small amounts that is far
  looser than 2 %. The 15 % clustering stays as it is; the
  tighter band is a condition on the weekly cadence only.
- The skipped-period allowance stays (a cleaner who misses a week is still recurring), and the
  75 % share of fitting gaps stays.
- Rejected: "a merchant whose rows spread over several amount clusters is variable spending" —
  it would unflag Amazon Prime for anyone who also shops at Amazon.

### 3. Yearly cadence — two same-amount charges (`transaction/domain/recurring.py`)

A cluster is a yearly series when its gaps fit `yearly` (350–380 days, or twice that) as now and
either:
- it has **2 rows within 2 % of the seed (≥ €0.10 slack)** — the same fixed-amount test as
  weekly — **and the merchant has no other row on the same side (money in or out) between
  them**; or
- it has **3 rows** in the usual 15 % band (unchanged; keeps a subscription whose price rose).

A yearly bill that varies (an insurance renewal) still needs its third year, or the user's tick.
D6's reason for three rows (two similar shop purchases a year apart, a false positive) is met by
the 2 % band together with the no-other-charges condition: the seed has a leisure venue visited
12 times a year where two visits 372 days apart are both €7.42, which no band can tell apart. Real
annual bills come from merchants the user pays for nothing else. Prime at Amazon, where the user
also shops, waits for its third year, as today.

How the cadence table expresses "fixed amount, fewer rows" is the builder's call (e.g. a
`fixed_min_rows` beside `min_rows`, with weekly having only the fixed form). The 2 %/€0.10 band
is one constant pair shared by weekly and yearly.

### 4. Hidden subscriptions — one untick excludes the merchant (`analytics/domain/recurring.py`)

- A merchant with **any** active expense row where `recurring_source = user` and
  `is_recurring = false` is never a hidden-subscription candidate, across the user's whole
  history (as "never flagged" already is). The web edit form sends `is_recurring` only when the
  user changes it, so such a row is always a deliberate untick.
- Why one row: a hidden subscription is judged across the whole merchant (every charge within
  10 % of the median), so no separate subscription at the same merchant could still deserve
  suggesting; requiring every row would make the user untick a dozen rows.
- Plumbing:
  - `AnalysisRow` (`transaction/schemas.py`) gains `recurring_source: str = "detected"` —
    defaulted, so the cleanup's bundle and existing constructors are unchanged (condition 3).
    `transaction_repository.list_active_rows_for_analysis` selects the column.
  - The analytics `Row` protocol (`analytics/domain/_aggregate.py`) gains the property.
  - The test helper `tests/unit/modules/analytics/rows.py`: its `Row` dataclass gains
    `recurring_source: str = "detected"` as the last field, and `row()` a keyword to set it;
    existing calls are unchanged.
  - The `detected`/`user` values are `DETECTED`/`USER` in `transaction/domain/recurring.py`;
    analytics may import them through `app.modules.transaction`'s public exports (it already
    imports `MIN_DATE`/`MAX_DATE` that way) if the module contracts allow, otherwise the
    builder picks the cleanest route.

### 5. Date bounds on add and edit (`transaction/schemas.py`)

- `TransactionCreate.date` and `TransactionUpdate.date` must lie within
  `MIN_DATE`–`MAX_DATE` (1900-01-01 to 2100-12-31, `transaction/domain/dates.py`); outside is a
  422 on the date field, through the normal request-validation path.
- The web's add/edit form shows that error on the date field; the builder checks how the form
  surfaces a 422 today and does the least that makes the message appear there (and may add
  `min`/`max` to the date input).

### 6. The seed leaves "not recurring" to the rule (`server/scripts/seed_transactions.py`)

A seed row whose recurring cell is `true` is stored as the user's tick (`is_recurring = true`,
`recurring_source = user`); every other row is `detected` and judged by the rule, as an import
with a blank cell is. Today every seed row is `user`, so under rule 4 every unflagged seed
merchant would be hidden from hidden subscriptions forever, and the new cadences would never run
on seed data. The seed must pass through the same write path that runs the rule (it uses
`import_many` with `TransactionImport`; `is_recurring = None` is "leave it to the rule").

## Tests first

Each bug's reproduce case is written as a failing test before the fix:

- **Laptop:** about 4 electronics expenses in the 30 days before, plenty of other one-off
  spending, then €1,249 in electronics → an outlier with `compared_with = "all"`. Also, in the
  fallback: a thin-category purchase above the z-threshold but under 5 % of average monthly
  spend is **not** flagged; a large `atm` or `savings_investments` row in a thin window is
  **not** flagged; a dense category behaves as before (`compared_with = "category"`).
- **Lidl:** a dozen rows at one merchant, €38–€46, gaps of 5–9 days → no row recurring. Also: a
  fixed weekly charge with 4 rows → recurring; with 3 → not; a fixed weekly charge with one
  skipped week → recurring.
- **Yearly:** two charges ~365 days apart at the same amount → recurring; two that differ by
  10 % → not; two identical charges with other charges at the merchant between them → not
  (the €7.42 venue); three within 15 % → recurring (unchanged).
- **Hidden subscription:** a subscription-like merchant with one `user`/`false` row → not
  suggested; the same merchant without it → suggested.
- **Seed:** a `true` cell is stored `user`/`true`; a `false` cell is stored `detected`.
- **Date bounds:** create and update with a date in 1899 or 2101 → 422; on the bounds → accepted.
- The existing tests in `tests/unit/modules/transaction/domain/test_recurring.py` and
  `tests/unit/modules/analytics/test_anomalies.py` / `test_recurring.py` that encode the old
  thresholds are updated, not deleted, where the rule changed on purpose.

## Docs, in the same PR

- `docs/product/features/analytics.md` §3: the outlier bullet (fallback, `compared_with`) and the
  hidden-subscription bullet (the untick).
- `docs/data-model/transaction.md` D6: the cadence table (weekly 4 rows and fixed amount; yearly
  2 at a fixed amount or 3), replacing the "three rows, not two" paragraph with the reason for
  the change and today's date; a note that existing flags were not re-judged and why; and the
  seed sentence ("the seed script passes a bool, so its rows are `user`") changed to rule 6.
- `docs/BUGS.md`: remove the two bugs. `docs/TODO.md`: remove the three entries; add one for
  insights wording outliers by `compared_with`.
- `docs/ROADMAP.md`: this row to `complete` with the PR link. The spec and plan are deleted in
  the PR that completes the step (CLAUDE.md, *Specs and plans*).

## Left to the builder

- How the fallback is structured in `anomalies.py` (e.g. scoring all one-off expenses once and
  looking up each thin-category candidate's all-spending score), keeping it O(n log n) as now.
- How the cadence table encodes the fixed-amount condition.
- Exact test fixtures and names, and the import route for the `detected`/`user` constants.

## Constraints

- BRIEF §3 conditions 1–6. `analytics/schemas.py` is shared with the cleanup (it owns
  `MonthToDateResponse`); this branch only touches `OutlierResponse` there.
- Server conventions in `server/CLAUDE.md` and the `server-patterns` / `server-testing` skills.
