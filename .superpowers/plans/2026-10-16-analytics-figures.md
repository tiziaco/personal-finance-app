# Analytics figures Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every analytics figure is computed over finished calendar months with a month-to-date beside them, the misleading measures are fixed, and every figure 5b's `/analytics` page shows comes from the server.

**Architecture:** A new `domain/period.py` resolves a request (`months`, or bounds, or neither) plus the user's rows and today into a `Period` of `PeriodMonth`s, each whole or partial with a weight. The service loads the user's whole history once, resolves the period, and hands rows + period to each domain function; domain functions filter by the period and may reach back before it. Response schemas mirror domain dataclasses field for field (`test_schemas.py` enforces it).

**Tech Stack:** Python 3.13, FastAPI, Pydantic v2, `decimal`, pytest (unit: plain rows; integration: testcontainers Postgres).

**Spec:** `.superpowers/specs/2026-10-16-analytics-figures-design.md` — read §3 (periods) before any task; §4 is the field list each task implements.

## Global Constraints

- Touch only `server/app/modules/analytics/`, `server/tests/{unit,integration}/modules/analytics/`, `server/openapi.json`, `web-app/packages/api-client/src/generated/` (via `make gen-contract` only) and the docs in Task 11. Nothing under `web-app/apps/web/`, no other module, no migration.
- Every `AnalyticsService` method keeps its name and parameters.
- Money: `Decimal`, quantised to cents **half-up**; percent: `float` 0–100 rounded to 2 dp; nothing to divide by → `None`.
- Average month length: `Decimal("30.436875")` (365.2425 ÷ 12), named `AVERAGE_MONTH_DAYS` in `_aggregate.py`.
- `months`: integer 1–120; with `date_from` or `date_to` → `InvalidDateRangeError` (422, `INVALID_DATE_RANGE`).
- Domain tests pin `today = dt.date(2026, 10, 16)` (a Friday; 1 Jul 2026 is a Wednesday). Route tests pin it by monkeypatching `app.modules.analytics.service._today`.
- Commands run from `server/`. Unit: `APP_ENV=test uv run pytest tests/unit/modules/analytics -m unit -q`. Integration (needs Docker): `APP_ENV=test uv run pytest tests/integration/modules/analytics -m integration -q`.
- Commit after every task; message style `Analytics: <what>` (see `git log`).

## Review Focus

1. **A period crossing a year boundary** (anchor December, previous period and rolling average reaching into the year before) — months must step across years. Test in Task 1 and Task 3.
2. **Month-to-date on the 31st against a shorter month** (through 31 Mar → previous 1–28 Feb, or 29 in 2028) — clamp, don't crash. Test in Task 3.
3. **A user with exactly one usable row** — every endpoint returns a one-month partial period, no division by zero. Test in Task 3 (spending) and Task 9 (dashboard).
4. **`months` larger than the history** (`months=120`, five months of data) — clipped; the echo shows the real span. Test in Task 1.
5. **A one-day explicit range** — weight `1/days_in_month`, averages scale up, nothing null that has a denominator. Test in Task 1.

---

### Task 1: Half-up rounding and the period resolver

**Files:**
- Modify: `server/app/modules/analytics/domain/_aggregate.py` (`money`, add `AVERAGE_MONTH_DAYS`, `month_end`)
- Create: `server/app/modules/analytics/domain/period.py`
- Test: `server/tests/unit/modules/analytics/test_period.py`, `test_aggregate.py` (add rounding test)

**Interfaces:**
- Produces, in `period.py`:
  - `FIRST_MONTH_GRACE_DAYS = 7`
  - `@dataclass(frozen=True) class PeriodMonth: start: dt.date; first_day: dt.date; last_day: dt.date; partial: bool; weight: Decimal` (`start` is the 1st; `weight` = days ÷ days in month, `Decimal(1)` when whole)
  - `@dataclass(frozen=True) class Period: first_day: dt.date; last_day: dt.date; months: tuple[PeriodMonth, ...]` with methods `weight() -> Decimal` (sum of weights), `whole_months() -> tuple[PeriodMonth, ...]`, `contains(day: dt.date) -> bool`, `rows(rows: Iterable[R]) -> list[R]` (rows dated inside)
  - `usable_rows(rows: Iterable[R], today: dt.date) -> list[R]` — rows dated ≤ `month_end(today)`
  - `data_span(rows, today) -> Optional[tuple[dt.date, dt.date]]` — first and last usable day
  - `anchor_month(rows, today) -> Optional[dt.date]` — latest finished month holding a usable row, else today's month if it holds one, else `None`
  - `calendar_month(month: dt.date, rows, today) -> Optional[PeriodMonth]` — that month as the data sees it (rules 2 and 3 of spec §3.2; `None` before the data's first month or after its last). Used for reach-back.
  - `resolve_period(rows, today, *, date_from=None, date_to=None, months=None) -> Optional[Period]`
  - `previous_period(period: Period, rows, today) -> Optional[Period]` — when `period` is month-aligned (first day is a 1st, last day a month end) the same number of months before; otherwise the same number of days before; resolved through `resolve_period` with explicit bounds, and `None` when no usable row falls inside.
- Produces, in `_aggregate.py`: `AVERAGE_MONTH_DAYS`, `month_end(day) -> dt.date`.

- [ ] **Step 1: Write the failing tests** — `test_period.py`, with `TODAY = dt.date(2026, 10, 16)` and rows: first row `2026-03-12`, one expense per month through September, `2026-10-03`, and a typo row `2027-01-05`:
  - `anchor_month(ROWS, TODAY) == dt.date(2026, 9, 1)`; with only `2026-10-02`/`2026-10-05` rows it is `dt.date(2026, 10, 1)`; with no rows `None`.
  - `resolve_period(ROWS, TODAY, months=3)`: `first_day == 2026-07-01`, `last_day == 2026-09-30`, three whole months, `weight() == 3`.
  - default (no args): months March–September; March `first_day == 2026-03-12`, `partial`, `weight == Decimal(20) / Decimal(31)`.
  - `months=120`: same as default (clipped to March) — Review Focus 4.
  - `date_from=2026-08-15, date_to=2026-12-31`: August partial (17/31), September whole, October partial with `last_day == 2026-10-03` (3/31); the 2027 row is in no period.
  - `date_from=2025-01-01, date_to=2026-04-30`: starts `2026-03-12` (clip, then rule 3).
  - `date_from=2026-09-10, date_to=2026-09-10`: one month, `weight == Decimal(1) / Decimal(30)` — Review Focus 5.
  - wholly outside (`date_from=2027-02-01`; `date_to=2025-12-31`) → `None`; no rows → `None`.
  - only-October rows, `months=3`: one month, October, `partial`, `first_day == 2026-10-01`, `last_day == 2026-10-05`.
  - a gap: rows only in March and September, `date_from=2026-05-01, date_to=2026-06-30` → May and June, whole.
  - `previous_period(months=3 period)` → July–September gives April–June; `previous_period` of `2026-08-15..2026-09-20` (37 days) gives `2026-07-09..2026-08-14`; a previous span before the data → `None`.
  - Year boundary (Review Focus 1): `today=2026-01-20`, rows Sep 2025–Jan 2026 → `months=3` is Oct–Dec 2025; its previous period is Jul–Sep 2025 clipped to September.
  - `calendar_month(dt.date(2028, 2, 1), rows starting 2028-02-10, today=2028-02-20)` → partial, first `2028-02-10`, last = last row day, denominators use 29 days.
- [ ] **Step 2:** In `test_aggregate.py` add `test_money_rounds_half_up`: `money(Decimal("0.125")) == Decimal("0.13")`, `money(Decimal("0.525")) == Decimal("0.53")`, `money(Decimal("-0.125")) == Decimal("-0.13")`.
- [ ] **Step 3: Run** `APP_ENV=test uv run pytest tests/unit/modules/analytics/test_period.py tests/unit/modules/analytics/test_aggregate.py -m unit -q` — expect import errors / the rounding test failing.
- [ ] **Step 4: Implement.** `money` uses `quantize(CENT, rounding=ROUND_HALF_UP)`. `resolve_period` follows spec §3.2 exactly: compute usable rows and the data's months; pick the month range (months → N ending at the anchor; bounds → clip to `[1st of first data month, min(month_end(last data month), month_end(today))]`; neither → first data month to anchor); then build each `PeriodMonth` applying the three partial rules (a bound cuts it; current month ends at the last usable row's day; data's first month starts at its first row when that is after day `FIRST_MONTH_GRACE_DAYS`). `period.py` must not import `schemas` (schemas import the domain; a cycle).
- [ ] **Step 5: Run** the same command — PASS; then the whole unit suite `APP_ENV=test uv run pytest tests/unit/modules/analytics -m unit -q` — existing tests that assert half-even cents may need their expected cents updated; update them, nothing else.
- [ ] **Step 6: Commit** `Analytics: half-up cents and the period resolver`.

### Task 2: `DateRange` validates itself and carries `months`

**Files:**
- Modify: `server/app/modules/analytics/schemas.py` (`DateRange`), `dependencies.py`
- Test: `server/tests/unit/modules/analytics/test_schemas.py` (add), `server/tests/integration/modules/analytics/test_routes.py` (add)

**Interfaces:**
- Produces: `DateRange(date_from: Optional[date] = None, date_to: Optional[date] = None, months: Optional[int] = None)` with a `model_validator(mode="after")` raising `InvalidDateRangeError` for: a bound outside `MIN_DATE`–`MAX_DATE`, `date_from > date_to`, `months` outside 1–120, `months` with either bound. `get_date_range` adds `months: Optional[int] = Query(None, ge=1, le=120, description="The last N finished months; not with date_from/date_to")` and only builds `DateRange`.

- [ ] **Step 1: Write failing tests.** Unit: `DateRange(date_to=dt.date(9999, 1, 1))`, `DateRange(date_from=dt.date(2026, 3, 2), date_to=dt.date(2026, 3, 1))`, `DateRange(months=0)`, `DateRange(months=121)`, `DateRange(months=3, date_from=dt.date(2026, 1, 1))` each raise `InvalidDateRangeError`; `DateRange(months=3)` is fine. Integration: for every ranged route, `params={"months": 3, "date_to": "2026-09-30"}` → 422 with `error == "INVALID_DATE_RANGE"`; `params={"months": 3}` → 200.
- [ ] **Step 2: Run** unit test file — FAIL.
- [ ] **Step 3: Implement** as in Interfaces. Pydantic v2 lets a non-`ValueError` exception raised in a validator propagate unchanged; `InvalidDateRangeError` is a `ServiceError`, so it reaches the error handler as today.
- [ ] **Step 4: Run** unit + integration route tests — PASS (existing range tests still pass).
- [ ] **Step 5: Commit** `Analytics: DateRange validates itself and takes months`.

### Task 3: Spending — weighted averages, the new figures, month-to-date

**Files:**
- Modify: `domain/spending.py`, `schemas.py` (spending section), `service.py`
- Test: `tests/unit/modules/analytics/test_spending.py`, `test_schemas.py` (PAIRS), `tests/integration/modules/analytics/test_routes.py`

**Interfaces:**
- Consumes: Task 1's `Period`, `PeriodMonth`, `resolve_period`, `calendar_month`, `usable_rows`, `AVERAGE_MONTH_DAYS`.
- Produces:
  - `MonthFlow(month, income, expenses, net, expense_change_pct, partial: bool, expenses_rolling_avg_3m: Optional[Decimal], savings_rate_pct: Optional[float])`
  - `LatestMonth(month: str, income, expenses, income_vs_average_pct: Optional[float], expenses_vs_average_pct: Optional[float])`
  - `MonthToDate(month: str, through: dt.date, income, expenses, previous_month: str, previous_income, previous_expenses, income_change_pct: Optional[float], expenses_change_pct: Optional[float])`
  - `SpendingSummary` fields in order: `date_from, date_to, total_income, total_expenses, net, transaction_count, average_income, average_expense, average_monthly_income, average_monthly_expenses, average_monthly_net, burn_rate, savings_rate_pct, months, latest_month: Optional[LatestMonth], month_to_date: Optional[MonthToDate]`
  - `monthly_flows(rows, months: Sequence[PeriodMonth], *, today: dt.date) -> tuple[MonthFlow, ...]` (Task 9 reuses it)
  - `month_to_date(rows, today: dt.date) -> Optional[MonthToDate]` (Task 9 reuses it)
  - `spending_summary(rows, period: Optional[Period], *, today: dt.date) -> SpendingSummary`
  - Schemas `MonthFlowResponse`, `LatestMonthResponse`, `MonthToDateResponse`, `SpendingResponse` mirror them (descriptions per spec §4.1; `burn_rate`: "Average monthly expenses minus average monthly income; negative while saving"; `average_income`/`average_expense`: "per transaction").
  - In `service.py`: `def _today() -> dt.date` (UTC date) and `async def _context(session, user_id, date_range) -> tuple[list[AnalysisRow], Optional[Period], dt.date]` that loads `MIN_DATE`–`MAX_DATE`, applies `usable_rows`, and resolves the period. Every later endpoint task uses `_context`.

- [ ] **Step 1: Write failing tests** with `TODAY = 2026-10-16` and rows: `2026-06-01 −800`; July and August: `−1000` on the 10th, `+2000` salary on the 25th; September: `−50` on the 1st, `−1250` on the 10th, `+2000` on the 25th; `2026-10-02 −100`.
  - `months=3`: totals income `6000.00`, expenses `3300.00`, net `2700.00`; `average_monthly_income 2000.00`, `average_monthly_expenses 1100.00`, `average_monthly_net 900.00`, `burn_rate −900.00`, `savings_rate_pct 45.0`; `date_from 2026-07-01`, `date_to 2026-09-30`.
  - months: July `expense_change_pct 25.0` (vs June, outside the period), rolling `None` (May is before the data); August rolling `933.33`; September `expense_change_pct 30.0`, rolling `1100.00`, `savings_rate_pct 35.0`; all `partial False`.
  - `latest_month == LatestMonth("2026-09", 2000.00, 1300.00, 0.0, 18.18)`.
  - `month_to_date == MonthToDate("2026-10", 2026-10-02, 0.00, 100.00, "2026-09", 0.00, 50.00, None, 100.0)`.
  - Partial bound: `date_from=2026-08-16, date_to=2026-09-30` → August `partial`, income `4000.00`, expenses `1300.00`, `average_monthly_income == 2638.30` (4000 ÷ 47/31), September `expense_change_pct None`, `latest_month.month == "2026-09"`.
  - Fallback: only `2026-10-02 −100` → one partial month, `latest_month None`, `average_monthly_expenses 1550.00` (100 ÷ 2/31), `savings_rate_pct None` — Review Focus 3.
  - Month-to-date clamp (Review Focus 2): `today=2026-03-31`, rows `2026-02-28 −10`, `2026-03-31 −20` → `previous_month "2026-02"`, `previous_expenses 10.00`.
  - Year boundary (Review Focus 1): `today=2026-01-20`, monthly expenses Sep–Dec 2025, `months=3` → October's `expense_change_pct` compares with September 2025.
  - Empty: `spending_summary([], None, today=TODAY)` → zeros, empty `months`, `latest_month None`, `month_to_date None`.
  - Add the new pairs to `test_schemas.py` PAIRS.
  - Integration: monkeypatch `_today` to `2026-10-16`; seed the same rows; `GET /spending?months=3` returns `date_from "2026-07-01"`, `average_monthly_net "900.00"` and a `month_to_date` with `through "2026-10-02"`.
- [ ] **Step 2: Run** `test_spending.py` — FAIL.
- [ ] **Step 3: Implement.** Averages divide totals by `period.weight()`. `expense_change_pct` and `expenses_rolling_avg_3m` look up neighbouring months with `calendar_month` (so they reach before the period) and return `None` if any month involved is partial or missing. `latest_month` is the last whole month in the period; its pcts use `pct_change(average, value)`. `month_to_date` uses today's month; `None` without a usable row in it.
- [ ] **Step 4: Run** unit + spending route tests — PASS. Existing spending tests that assumed whole-range months: update them to pass `resolve_period(...)` and the new values; don't delete a case without replacing it.
- [ ] **Step 5: Commit** `Analytics: spending over finished months, with month-to-date`.

### Task 4: Categories — previous period and the growth halves

**Files:** Modify `domain/categories.py`, `schemas.py` (categories), `service.py`. Test `test_categories.py`, `test_schemas.py`, `test_routes.py`.

**Interfaces:**
- Consumes: `Period`, `previous_period`, `_context`.
- Produces:
  - `CategorySpend(category, total, count, average, share_pct, previous_total: Optional[Decimal], change_pct: Optional[float])`
  - `CategoryTrend(category, earlier_monthly_average, later_monthly_average, change_amount, change_pct: Optional[float])` (old fields removed)
  - `CategoryBreakdown(date_from, date_to, previous_date_from, previous_date_to, total_expenses, top_categories, by_frequency, top_growing, top_declining)`
  - `category_breakdown(rows, period: Optional[Period], top_n: int = 10, *, today: dt.date) -> CategoryBreakdown`
  - Schemas mirror them.

- [ ] **Step 1: Write failing tests**, `TODAY = 2026-10-16`, rows (expenses, all on the 5th): groceries Jun 200, Jul 200, Aug 300, Sep 300; dining Jun 100, Jul 100; gym Aug 40, Sep 40.
  - `months=4` (Jun–Sep): `top_growing == (CategoryTrend("groceries", 200.00, 300.00, 100.00, 50.0), CategoryTrend("gym", 0.00, 40.00, 40.00, None))`; `top_declining == (CategoryTrend("dining", 100.00, 0.00, -100.00, -100.0),)`.
  - `months=3` (Jul–Sep, odd): earlier = July only, later = September only; groceries earlier `200.00`, later `300.00`.
  - `months=1`: both lists empty.
  - `months=2` (Aug–Sep): groceries `previous_total 400.00`, `change_pct 50.0`; gym `previous_total 0.00`, `change_pct None`; `previous_date_from 2026-06-01`, `previous_date_to 2026-07-31`; dining not listed.
  - `months=4`: previous Feb–May holds no rows → `previous_date_from None`, every `previous_total None`, `change_pct None`.
  - Ties in `change_amount` order by slug.
  - Integration: `GET /categories?months=2` echoes `date_from "2026-08-01"`.
- [ ] **Step 2: Run** — FAIL.
- [ ] **Step 3: Implement** per spec §4.2: halves from `period.whole_months()`; each half's average = its spend ÷ its month count; growing `change_amount > 0` ranked by `-change_amount`, declining `< 0` ranked by `change_amount`, both then by slug, top `TREND_SIZE` (5).
- [ ] **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `Analytics: category growth by halves, and change against the previous period`.

### Task 5: Merchants — period echo, no risk band

**Files:** Modify `domain/merchants.py`, `schemas.py` (merchants), `service.py`. Test `test_merchants.py`, `test_schemas.py`, `test_routes.py`.

**Interfaces:**
- Produces: `MerchantConcentration(top_5_share_pct, top_10_share_pct, herfindahl_index, unique_merchants)` (`risk`, `Risk`, `HIGH_CONCENTRATION`, `MEDIUM_CONCENTRATION` deleted); `MerchantBreakdown(date_from, date_to, total_expenses, top_by_spend, top_by_frequency, concentration)`; `merchant_breakdown(rows, period: Optional[Period], top_n: int = 15) -> MerchantBreakdown` (counts only rows inside the period).

- [ ] **Step 1: Write failing tests:** rows in June and September, `months=1` → only September's merchants, `date_from 2026-09-01`; `MerchantConcentration` has no `risk` field (`"risk" not in {f.name for f in fields(MerchantConcentration)}`); integration `GET /merchants?months=1` → 200 and no `risk` key under `concentration`.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement.** **Step 4: Run** — PASS (drop the old risk-band tests).
- [ ] **Step 5: Commit** `Analytics: merchants over the period; drop the risk band`.

### Task 6: Recurring — billing rhythm, active merchants, the hidden-subscription rule

**Files:** Modify `domain/recurring.py`, `schemas.py` (recurring), `service.py`. Test `test_recurring.py`, `test_schemas.py`, `test_routes.py`.

**Interfaces:**
- Produces:
  - `RecurringMerchant(merchant, charges, months_charged, median_charge, interval_days: Optional[int], monthly_cost, last_charge: dt.date, active: bool)`
  - `RecurringAnalysis(date_from, date_to, total_expenses, recurring_total, recurring_count, amount_share_pct, count_share_pct, monthly_recurring_cost, merchants, hidden_subscriptions)`; `HiddenSubscription` keeps its fields.
  - `recurring_analysis(rows, period: Optional[Period]) -> RecurringAnalysis`
  - Constants: `ACTIVE_GAP_FACTOR = Decimal("1.5")`, `HIDDEN_MIN_MONTHS = 3`, `HIDDEN_GAP_DAYS = (25, 35)`, `HIDDEN_AMOUNT_TOLERANCE = Decimal("0.10")`, `HIDDEN_MAX_CHARGE = Decimal("50.00")`, `MONTHLY_GAP_DAYS = 25`.
- **Refines spec §4.4's cost formula** (the user agreed a monthly/quarterly/yearly rhythm): with `interval_days ≥ MONTHLY_GAP_DAYS`, `cadence = max(1, round(interval_days / AVERAGE_MONTH_DAYS))` months and `monthly_cost = median_charge / cadence`, so €10 every 28–31 days is exactly €10.00 and €600 every 365 days is €50.00; below 25 days, `median_charge × AVERAGE_MONTH_DAYS / interval_days`; with one charge, `median_charge / period.weight()`. Update the spec's §4.4 line to match in this task's commit.

- [ ] **Step 1: Write failing tests**, `TODAY = 2026-10-16`, `months=12` unless stated (all flagged recurring unless stated):
  - Netflix `−10.00` on the 5th, Jan–Sep → `interval_days` 28–31 median, `monthly_cost 10.00`, `active True`.
  - Insurance `−600.00` once on `2026-02-14`, with Netflix from `2025-10-05` so the 12-month period (Oct 2025–Sep 2026) is whole → `monthly_cost 50.00`, `interval_days None`, `active True`.
  - Insurance `−600.00` on `2025-02-14` and `2026-02-14`, `date_from=2025-01-01` → `monthly_cost 50.00`.
  - Gym `−40.00` on the 5th, Jan–Mar only → `active False`; `monthly_recurring_cost` with Netflix + gym `== 10.00`.
  - Hidden: unflagged Spotify `−9.99` on the 3rd, Jun–Sep → listed; three coffees `−3.50` in August only → not listed; grocer `−35.00` weekly → not listed (gap 7); unflagged `−20/−45/−30` monthly → not listed (amounts vary > 10%); unflagged `−79.00` monthly → not listed (over €50).
  - Integration: `GET /recurring?months=3` → 200, echoes `date_from`.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement** per spec §4.4 and the refinement above; `active` compares `period.last_day − last_charge` with `ACTIVE_GAP_FACTOR × interval_days`. Rows outside the period are ignored. **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `Analytics: recurring cost by billing rhythm; hidden subscriptions look like subscriptions`.

### Task 7: Behaviour — weekday per day, whole-month seasonality and stability

**Files:** Modify `domain/behaviour.py`, `schemas.py` (behaviour), `service.py`. Test `test_behaviour.py`, `test_schemas.py`, `test_routes.py`.

**Interfaces:**
- Produces:
  - `WeekdaySpend(weekday, name, total, count, average, share_pct, days: int, per_day: Decimal)`
  - `MonthOfYear(month, average_spend, index, years: int)`
  - `CategoryStability(category, count, months: int, cv, stability)`
  - `Behaviour(date_from, date_to, by_weekday, weekday, weekend, weekend_bias_pct, seasonality, stability, stable_share_pct, moderate_share_pct, volatile_share_pct, expense_change_pct)`
  - `behaviour_analysis(rows, period: Optional[Period]) -> Behaviour`; `STABILITY_MIN_MONTHS = 3` replaces `STABILITY_MIN_EXPENSES`.

- [ ] **Step 1: Write failing tests**, `TODAY = 2026-10-16`:
  - `months=3` (Jul–Sep, 92 days from a Wednesday): Wednesday `days == 14`, every other weekday `13`; `per_day == total / days` to the cent.
  - €10 a day from `2026-03-12` to `2026-10-03`, default period: March `years 0`, `index None`; April `years 1`, `average_spend 300.00`, `index 98.36` (300 ÷ mean of 300,310,300,310,310,300); October not in the period → `years 0`; `expense_change_pct == -3.23` (August 310 → September 300).
  - Groceries 300 every month Jun–Sep made of 5/20/125/150 → `stability "stable"`, `cv 0.0`, `months 4`; a category with two months → not classified.
  - `weekend_bias_pct` with `€0.01` on a weekday and `€0.03` on a weekend day in one week is not `None`.
  - Integration: `GET /behaviour?months=3` echoes `date_from`.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement** per spec §4.5: weekday `days` and the weekday/weekend parts count calendar days from `period.first_day` to `period.last_day`; seasonality and stability use `period.whole_months()` only (stability from each category's first whole month with spend); `weekend_bias_pct` from unrounded per-day values. **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `Analytics: behaviour over whole months; spend per weekday occurrence`.

### Task 8: Anomalies — category outliers, clipped spikes ranked in €

**Files:** Modify `domain/anomalies.py`, `schemas.py` (anomalies), `service.py`. Test `test_anomalies.py`, `test_schemas.py`, `test_routes.py`.

**Interfaces:**
- Produces:
  - `CategorySpike(category, recent_total, baseline_30d, increase_amount, spike_pct)`
  - `Anomalies(date_from, date_to, std_threshold, window_days, outliers, spikes, spike_window_start, spike_window_end)`
  - `find_anomalies(rows, period: Optional[Period], std_threshold: float = 2.5, window_days: int = 30) -> Anomalies`; `SPIKE_MIN_SHARE_OF_MONTH = Decimal("0.05")`.

- [ ] **Step 1: Write failing tests**, `TODAY = 2026-10-16`:
  - Rent `−900` flagged recurring on the 1st of each month Apr–Sep among daily groceries `−10…−40` → no outlier is rent.
  - Dining `−30…−50` twice a week Jul–Sep and one `−400` dining on `2026-09-20`, `months=1` → that row is an outlier (its window reaches into August); `window_mean` is the dining window's mean.
  - Gifts `−10` in January and `−40` in the last 30 days, groceries steady → gifts not a spike (increase under 5% of average monthly spend).
  - Groceries ~€300 a month Jun–Aug and €700 in the last 30 days → a spike with `increase_amount > 0`; spikes ordered by `increase_amount` descending.
  - Groceries steady €300 Jun–Oct with `date_from=2026-01-01` → no spike (the period clips to June).
  - Data spanning 40 days → `spikes == ()`, `spike_window_start is None`, `spike_window_end is None`.
  - Integration: `GET /anomalies?months=3` echoes `date_from`.
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement** per spec §4.6: outlier candidates are period rows; windows draw on all non-recurring expenses of the same category (prefix sums per category, as today's algorithm, run once per category); spike window ends at `period.last_day`, baseline from `period.first_day`; flag when `pct > SPIKE_MIN_PCT` and `increase_amount ≥ SPIKE_MIN_SHARE_OF_MONTH × (period expenses ÷ period.weight())`. **Step 4: Run** — PASS.
- [ ] **Step 5: Commit** `Analytics: outliers within category, spikes clipped to the data and ranked in euros`.

### Task 9: Dashboard — the anchor month, month-to-date, a clamped trend

**Files:** Modify `domain/dashboard.py`, `schemas.py` (dashboard), `service.py` (dashboard uses `_today()`). Test `test_dashboard.py`, `test_schemas.py`, `test_routes.py` (existing dashboard tests).

**Interfaces:**
- Consumes: `anchor_month`, `usable_rows`, `calendar_month`, `monthly_flows`, `month_to_date`.
- Produces: `Dashboard(reference_month, reference_partial: bool, total_spent, recurring_spent, recurring_count, net_balance, average_cashflow, cashflow_months, spending_by_category, monthly_trend, month_to_date: Optional[MonthToDate])`; `build_dashboard(rows, *, today)` unchanged signature; `EMPTY` updated.

- [ ] **Step 1: Write failing tests**, `TODAY = 2026-10-16`:
  - Rows Aug–Sep plus `2026-10-02` → `reference_month "2026-09"`, `reference_partial False`, `month_to_date.month "2026-10"`.
  - Rows only in September → `monthly_trend` has one point (`"2026-09"`), not six.
  - Only `2026-10-02` → `reference_month "2026-10"`, `reference_partial True` (Review Focus 3).
  - A row dated `2027-01-05` plus September rows → `reference_month "2026-09"`; only a `2027-01-05` row → `reference_month None` (future rows are unusable).
  - Integration: update `test_empty_dashboard`'s expected body with `reference_partial: False` and `month_to_date: None`; pin `_today` in the existing dashboard test and keep its assertions (reference month September).
- [ ] **Step 2: Run** — FAIL. **Step 3: Implement**: reference = `anchor_month(rows, today)`; trend months from `max(first data month, reference − 5)`; cashflow as today over months to the reference. **Step 4: Run** unit + integration — PASS.
- [ ] **Step 5: Commit** `Analytics: dashboard anchors on the latest finished month`.

### Task 10: Contract, descriptions, full checks

**Files:** Modify `schemas.py` (descriptions only), `router.py` (route descriptions mention `months`), `server/openapi.json`, `web-app/packages/api-client/src/generated/**` (generated).

- [ ] **Step 1:** Sweep `schemas.py` and `router.py` descriptions against spec §4–§5 (growth item, `MonthOfYearResponse.index` null rules, spike window null = not checked, `burn_rate` sign, per-transaction averages, every `date_from`/`date_to` echo: "First/last day of the resolved period; null when empty").
- [ ] **Step 2: Run** `make gen-contract` from the repo root; expect `server/openapi.json` and the generated client to change.
- [ ] **Step 3: Run** `make check-server` and `make check-web` from the repo root — both pass (web compiles against the regenerated client; the dashboard reads only fields that keep their types). If `check-web` fails on a removed field, stop and report it: web code is not ours to edit.
- [ ] **Step 4: Run** the full analytics suites (unit + integration) and `APP_ENV=test uv run pytest tests/unit/test_module_contracts.py -q` — PASS.
- [ ] **Step 5: Commit** `Analytics: regenerate the contract`.

### Task 11: Docs

**Files:** Modify `docs/product/features/analytics.md`, `docs/TODO.md` (line ~164), `docs/ROADMAP.md` (decision note only; the row's state changes at PR time).

- [ ] **Step 1:** `analytics.md` §2: dashboard reference month = latest finished month with data (else the month in progress, marked), month-to-date; analytics page periods (finished months; 1/3/6, 3/6/12, 4/6/12/24 by tab). §3: every rule from spec §3 and §4 (periods, partial months and weights, rounding half-up, recurring rhythm and active, hidden-subscription rule, stability over monthly totals, outliers within category, spike floor and € ranking, growth halves, previous period). §5: the risk label is gone. §6: savings rate answered (added); the 15 Oct dashboard decision marked **reversed on 16 Oct 2026** — imports lag and a partial month read as a collapse; finished months plus month-to-date is the standard.
- [ ] **Step 2:** `TODO.md`: the month-picker line says "latest finished month". `ROADMAP.md`: add under the ordering notes "**Analytics periods are finished months** (product; 16 Oct 2026)" with one sentence of why.
- [ ] **Step 3: Commit** `Docs: analytics periods, measures and the reversed dashboard decision`.
