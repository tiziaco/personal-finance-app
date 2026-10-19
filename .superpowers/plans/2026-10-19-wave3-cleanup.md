# Wave 3 cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One history load per analytics caller, the month-to-date rule in one place, no monthly
average for a period without a whole month, the web plumbing fixes, and three folded-in
bugs/tests — with no other behaviour change.

**Architecture:** A new `AnalyticsHistory` (in `analytics`) holds one user's usable rows and today,
loaded once, and computes every existing analysis for any `DateRange` in memory, returning the
existing response models. `AnalyticsService`'s route methods become "load a history, call it";
`insights/figures.py` loads one history and picks its windows from it. It is general (any window,
any analysis) rather than insights-shaped, so step 7's chat tools take the same object.
`MonthToDateResponse` gains `previous_through` and `net`, and the web stops computing either.

**Tech Stack:** FastAPI, Pydantic v2, pytest (testcontainers Postgres); Next.js, TanStack Query v5,
nuqs 2, Vitest + Testing Library.

**Spec:** `.superpowers/specs/2026-10-19-wave3-cleanup-design.md` — read it before any task.

## Global Constraints

- Never modify `server/app/modules/analytics/domain/anomalies.py`, `analytics/domain/recurring.py`, or anything under `server/app/modules/transaction/` (another branch owns them).
- Construct `AnalysisRow` only with its current fields; the parallel branch may add defaulted ones.
- Never hand-edit `server/openapi.json` or `web-app/packages/api-client/src/generated/`; run `make gen-contract` from the repo root and commit its output with the schema change.
- No behaviour change outside spec §4 — same data, same responses, same insights input, apart from the new `previous_through`/`net` fields and the §4 nulls.
- Server conventions: `server-patterns` and `server-testing` skills; web: `web-app-patterns` and `web-app-testing` skills. Load the relevant one before each task.
- Server tests run from `server/`: `APP_ENV=test uv run pytest <path> -v`. Web tests from `web-app/`: `pnpm -s test <path>`. Before each commit: `make check-server` and/or `make check-web` from the repo root, as the task touches either.
- Copy fixed by the spec: the Flow tab's null-average line reads exactly `No full month yet`.

## Review Focus

1. **Month-end clamping:** a month-to-date through the 31st compares with the previous month's last day (30th, or 28th/29th in February) — Task 2 and Task 6 pin 31 Mar → 28 Feb and 31 Oct → 30 Sep.
2. **A period that is one partial *past* month** (data begins 20 Sep, nothing in October): averages are null, not scaled — Task 3 pins it.
3. **An empty period** (no rows): averages stay `0.00`, not null — the empty-period contract is unchanged — Task 3 pins it.
4. **The insights input for a one-month user and a user whose reference month is the month in progress** is the same as before the rewrite (spike window over 2 months; `reference_through`; no `month_to_date`) — Task 5's equivalence check and existing tests cover it.
5. **A period switch while the old period is shown:** the old figures stay, dimmed and `aria-busy`, and a first load still shows skeletons, not an empty dimmed page — Task 8 pins both.

---

### Task 1: Rate-limit fixture and the 429 test

**Files:**
- Modify: `server/tests/conftest.py` (beside `reset_app_state`)
- Test: `server/tests/integration/modules/conversation/router/test_conversation.py`

**Interfaces:**
- Produces: an autouse fixture `reset_rate_limits` in `server/tests/conftest.py`.

- [ ] **Step 1: Write the failing test** — in the rename test class, `test_a_rename_past_the_chat_limit_is_429`: parse the limit count from `settings.rate_limits.endpoints.CHAT[0]` (a string like `"100 per minute"`; take the leading integer), PATCH `/api/v1/conversation/conversation/{id}/name` with `data={"name": "n"}` that many times asserting each is 200, then once more asserting `status_code == 429`. Use `authenticated_client` and `user_conversation`.
- [ ] **Step 2: Run it; confirm it fails with a 500** (`AttributeError: 'State' object has no attribute 'limiter'`), per `docs/BUGS.md`.
  Run: `APP_ENV=test uv run pytest tests/integration/modules/conversation/router/test_conversation.py -k past_the_chat_limit -v`
- [ ] **Step 3: Add the autouse fixture** `reset_rate_limits()` in `server/tests/conftest.py`: sets `app.state.limiter = limiter` (from `app.core.limiter`) and calls `limiter.reset()` before every test.
- [ ] **Step 4: Run the test (PASS), then the whole server suite** (`make test` from `server/`) — all pass.
- [ ] **Step 5: Commit** — `Tests: an autouse fixture resets the rate limiter; a tripped limit is a 429, not a 500`. Leave the BUGS.md entry for Task 14.

---

### Task 2: `previous_through` and `net` on month-to-date

**Files:**
- Modify: `server/app/modules/analytics/domain/spending.py` (`MonthToDate`, `month_to_date`)
- Modify: `server/app/modules/analytics/schemas.py` (`MonthToDateResponse`)
- Test: `server/tests/unit/modules/analytics/test_spending.py`, `server/tests/integration/modules/analytics/test_routes.py`
- Regenerate: `server/openapi.json`, `web-app/packages/api-client/src/generated/`

**Interfaces:**
- Produces: `MonthToDate.previous_through: dt.date` and `MonthToDate.net: Decimal` (after `through` and `expenses` respectively is fine); `MonthToDateResponse.previous_through: dt.date` (description: "The last day of the previous month's comparison window: through's day, clamped to that month's length") and `MonthToDateResponse.net: Decimal` (description: "income − expenses"). Both appear in the dashboard's and spending's `month_to_date`.

- [ ] **Step 1: Write the failing unit tests:**
  - `test_month_to_date_names_the_previous_window_and_net`: with `ROWS` and `TODAY` (2026-10-16), `month_to_date(ROWS, TODAY)` has `previous_through == dt.date(2026, 9, 2)` and `net == Decimal("-100.00")`.
  - `test_month_to_date_clamps_previous_through_to_the_month_s_length` (parametrized): rows `row("2026-02-10", "-10.00")`, `row("2026-03-31", "-10.00")`, today `2026-03-31` → `previous_through == dt.date(2026, 2, 28)`; rows `row("2026-09-10", "-10.00")`, `row("2026-10-31", "-10.00")`, today `2026-10-31` → `dt.date(2026, 9, 30)`.
- [ ] **Step 2: Run; confirm they fail** (no attribute).
- [ ] **Step 3: Add the two fields** to `MonthToDate` and set them in `month_to_date` (`previous_through` is the local already computed; `net = money(income - out)`). Add them to `MonthToDateResponse`.
- [ ] **Step 4: Extend the route test** in `test_routes.py` that already checks a dashboard or spending `month_to_date`: assert `previous_through` and `net` are present with the expected strings.
- [ ] **Step 5: Run the analytics and insights tests** — `APP_ENV=test uv run pytest tests/unit/modules/analytics tests/integration/modules/analytics tests/integration/modules/insights -v` — PASS.
- [ ] **Step 6: `make gen-contract`** from the repo root; `make check-web` still passes (the new fields are additive).
- [ ] **Step 7: Commit** schema, domain, tests and the regenerated contract — `Analytics: month-to-date carries previous_through and net`.

---

### Task 3: No monthly average without a whole month

**Files:**
- Modify: `server/app/modules/analytics/domain/spending.py` (`SpendingSummary`, `spending_summary`)
- Modify: `server/app/modules/analytics/schemas.py` (`SpendingResponse`)
- Test: `server/tests/unit/modules/analytics/test_spending.py`, `server/tests/integration/modules/analytics/test_routes.py`
- Regenerate: the contract

**Interfaces:**
- Produces: `SpendingSummary.average_monthly_income/expenses/net` and `burn_rate` are `Optional[Decimal]`; same on `SpendingResponse`, each description gaining "; null when the period has no whole month". Rule: `period is None` → `ZERO` (unchanged); `period.whole_months()` empty → `None`; otherwise unchanged.

- [ ] **Step 1: Change the existing test** `test_only_this_months_data_is_one_partial_month`: the three averages and `burn_rate` are `None`. Keep its other assertions.
- [ ] **Step 2: Write the failing tests:**
  - `test_one_partial_past_month_has_no_monthly_average`: rows `row("2026-09-20", "-300.00")`, `row("2026-09-25", "1000.00", category="salary")`; `summary(rows=those, months=1)` → period 2026-09-20 to 2026-09-30, partial; all four fields `None`; `total_expenses == Decimal("300.00")`.
  - `test_a_range_shorter_than_a_month_has_no_monthly_average`: `summary(date_from=dt.date(2026, 9, 1), date_to=dt.date(2026, 9, 15))` → all four `None`.
  - Extend `test_empty_input_is_all_zero`: still `Decimal("0.00")` for the averages and `burn_rate` (Review Focus 3).
- [ ] **Step 3: Run; confirm the new ones fail.**
- [ ] **Step 4: Implement the rule** in `spending_summary`, computing the four once from `period.whole_months()`. `_latest_month` already returns `None` here; it never sees a null average.
- [ ] **Step 5: Update `SpendingResponse`** types and descriptions; update any route test that asserted a scaled average for a partial-only period.
- [ ] **Step 6: Check the insights prompt** `server/app/agents/insights/prompts/v1.md` reads a null average correctly ("a user with one month has none"). Change nothing unless it would quote a null; note the finding in the commit body.
- [ ] **Step 7: Run analytics + insights tests; `make gen-contract`.** `make check-web` may now fail type-check in `flow-tab.tsx` (`string | null`) — expected; Task 7 fixes it. Commit (pre-commit checks only the contract); do not push until Task 7 is in.
- [ ] **Step 8: Commit** — `Analytics: no monthly average or burn rate for a period without a whole month`.

---

### Task 4: `AnalyticsHistory` — one load, every analysis

**Files:**
- Create: `server/app/modules/analytics/history.py`
- Modify: `server/app/modules/analytics/service.py`, `server/app/modules/analytics/__init__.py` (export `AnalyticsHistory`)
- Test: `server/tests/unit/modules/analytics/test_history.py` (unit, rows built with `tests/unit/modules/analytics/rows.row`), `server/tests/integration/modules/analytics/test_service.py` (create if absent)

**Interfaces:**
- Produces, in `history.py`:
  ```python
  @dataclass(frozen=True)
  class AnalyticsHistory:
      """One user's usable rows and today, loaded once; every analysis over any window, in memory."""
      rows: tuple[AnalysisRow, ...]   # already usable_rows(...)-filtered
      today: dt.date
      def period(self, date_range: DateRange) -> Optional[Period]
      def dashboard(self) -> DashboardResponse
      def spending(self, date_range: DateRange) -> SpendingResponse
      def categories(self, date_range: DateRange, top_n: int) -> CategoryBreakdownResponse
      def merchants(self, date_range: DateRange, top_n: int) -> MerchantBreakdownResponse
      def recurring(self, date_range: DateRange) -> RecurringResponse
      def behaviour(self, date_range: DateRange) -> BehaviourResponse
      def anomalies(self, date_range: DateRange, std_threshold: float, window_days: int) -> AnomaliesResponse
  ```
  Each method is the body of today's matching `AnalyticsService` method minus the load (same domain call, same `model_validate`, `from_attributes=True` where today uses it).
- Produces, in `service.py`: `AnalyticsService.history(session, user_id) -> AnalyticsHistory` (async; one `transaction_service.list_for_analysis(session, user_id, MIN_DATE, MAX_DATE)`, one `_today()`, `usable_rows`). Every existing method keeps its signature and becomes `return (await AnalyticsService.history(session, user_id)).<method>(...)`. Delete `_rows` and `_context`. Keep `_today` in `service.py` — tests monkeypatch `service._today`.
- `dashboard` today loads rows without `usable_rows`; `build_dashboard` filters them itself, so passing usable rows is equivalent.

- [ ] **Step 1: Write the failing unit tests** in `test_history.py`: for `ROWS`-style data and `TODAY`, each `AnalyticsHistory` method equals the domain function's result validated into its response (e.g. `history.spending(DateRange(months=3)) == SpendingResponse.model_validate(spending_summary(rows, resolve_period(rows, TODAY, months=3), today=TODAY))`); `history.period(DateRange(months=3))` equals `resolve_period(...)`.
- [ ] **Step 2: Write the failing integration test** `test_history_loads_rows_once`: spy on `transaction_service.list_for_analysis` (monkeypatch with a counting wrapper); `history = await analytics_service.history(db_session, test_user.id)`; call `spending`, `categories`, `anomalies`, `dashboard` on it; assert one load.
- [ ] **Step 3: Run; confirm both fail.**
- [ ] **Step 4: Implement `history.py` and rewire `service.py`; export `AnalyticsHistory` from `analytics/__init__.py`.**
- [ ] **Step 5: Run the full analytics test tree** (unit + integration routes) unchanged — PASS; `make check-server` (import contracts) — PASS.
- [ ] **Step 6: Commit** — `Analytics: AnalyticsHistory loads a user's rows and today once`.

---

### Task 5: Insights figures onto one history

**Files:**
- Modify: `server/app/modules/insights/figures.py`
- Test: `server/tests/integration/modules/insights/test_figures.py`

**Interfaces:**
- Consumes: `analytics_service.history(...)`, `AnalyticsHistory` methods (Task 4); `MonthToDateResponse.previous_through` (Task 2).
- Produces: `gather_figures(session, user_id) -> Optional[InsightsInput]`, signature unchanged.

- [ ] **Step 1: Equivalence check (temporary, not committed).** Copy today's `figures.py` to `server/app/modules/insights/_figures_legacy.py`. Write a scratch test that, for each existing `test_figures.py` dataset plus one rich dataset (6+ months, salary, a recurring merchant, a spike, a month-to-date), asserts the new `gather_figures(...)` equals the legacy one — `figures` compared after dropping `previous_through` and `net` from every `month_to_date`, and after Task 3's nulls (both run on the same schemas, so these agree by construction). Run it after Step 3; delete both files before committing.
- [ ] **Step 2: Retarget the `anomaly_windows` spy** to `AnalyticsHistory.anomalies` (monkeypatch the class attribute; the spy takes `self`). Its assertions (`[1, 3]`, `[1, 2]`) stay.
- [ ] **Step 3: Rewrite `gather_figures`:** one `history = await analytics_service.history(session, user_id)`; `dashboard = history.dashboard()`; usual = `DateRange(months=BASELINE_MONTHS + 1)` (resolve_period clips it to the first month with data); the usual's month count for the spike window is `len(history.period(usual).months)`; same-days-previous range is `month_to_date.through.replace(day=1)`.. `month_to_date.through` and `previous_through.replace(day=1)`.. `month_to_date.previous_through`. Keep the anomalies merge (outliers of the reference month, spikes of `max(months, 2)`), the `seasonality` and `month_to_date` pops and every figures key, built from the typed models and dumped once per key. Delete `_usual_months`, `_month_index`, `_same_days_previous_month`, the second `spending` call and the `calendar` import if unused. Update the module docstring's window paragraph.
- [ ] **Step 4: Write the failing test** `test_a_generation_loads_rows_once`: counting spy on `transaction_service.list_for_analysis` and on `service._today`; one call each for a user with a month-to-date. (Write before Step 3 if you prefer; it must fail on the legacy code — it makes ~11 loads.)
- [ ] **Step 5: Run `test_figures.py` and the scratch equivalence test — PASS; delete the scratch test and `_figures_legacy.py`; run `tests/integration/modules/insights` — PASS; `make check-server`.**
- [ ] **Step 6: Commit** — `Insights: figures from one analytics history; the month-to-date window from analytics`.

---

### Task 6: Web month-to-date copies deleted

**Files:**
- Modify: `web-app/apps/web/src/components/dashboard/month-to-date-card.tsx`, `web-app/apps/web/src/components/analytics/month-to-date-strip.tsx`
- Test: `month-to-date-card.test.tsx`, `month-to-date-strip.test.tsx` (same folders)

**Interfaces:**
- Consumes: `MonthToDateResponse.previous_through: string` (ISO day) and `.net: string` from the regenerated client (Task 2).

- [ ] **Step 1: Write the failing tests:**
  - Card: through `2026-10-31`, `previous_through: "2026-09-30"` → the range text reads `1–31 Oct · vs 1–30 Sep`; `net: "-123.45"` renders `Net` with `formatAmount("-123.45")` (the server's value, not income − expenses: give fixtures where the two disagree to prove it).
  - Strip: through `2026-10-31`, `previous_through: "2026-09-30"` → the comparison names `formatDayRange`'s output for 1–30 September, not 1–31.
  - Update existing fixtures to include the two fields.
- [ ] **Step 2: Run; confirm they fail.**
- [ ] **Step 3: Card:** the previous range's day comes from `parseIsoDay(previous_through)`; render `monthToDate.net`; delete `daysInPrevious`, `previousDay`, the `Number(...)` net and `unsigned` (expenses are already positive). The current-month day and `daysInMonth` progress bar stay. **Strip:** the previous-month range comes from `previous_through`'s day. Adjust `formatDayRange`'s call (or signature) so it takes the day it is given.
- [ ] **Step 4: Run both test files, then `make test-web` — PASS.**
- [ ] **Step 5: Commit** — `Web: month-to-date's comparison window and net come from the server`.

---

### Task 7: Flow tab — "No full month yet"

**Files:**
- Modify: `web-app/apps/web/src/components/analytics/flow-tab.tsx` (`Figure`)
- Test: `web-app/apps/web/src/components/analytics/flow-tab.test.tsx`

**Interfaces:**
- Consumes: `SpendingResponse.average_monthly_*: string | null` (Task 3).

- [ ] **Step 1: Write the failing test** `shows "No full month yet" when the period has no whole month`: `DATA` with the three averages `null` and `burn_rate: null` → three `No full month yet` lines, muted (no amount class), and no `/ month` text; totals still render.
- [ ] **Step 2: Run; confirm it fails.**
- [ ] **Step 3: `Figure`'s `average` prop becomes `string | null`;** null renders `No full month yet` in `text-muted-foreground`.
- [ ] **Step 4: Run the file, then `make check-web` and `make test-web` — PASS** (this clears Task 3's type error).
- [ ] **Step 5: Commit** — `Web: the Flow tab shows no monthly average until a month is whole`.

---

### Task 8: `ANALYTICS_STALE_TIME` module, `keepPreviousData`, dimming

**Files:**
- Create: `web-app/apps/web/src/components/analytics/stale-time.ts` (exports `ANALYTICS_STALE_TIME = 2 * 60 * 1000`; no imports)
- Modify: `components/dashboard/home-dashboard.tsx` (import it; stop exporting it), `components/analytics/query.ts`, `components/analytics/query-gate.tsx`
- Test: `components/analytics/query-gate.test.tsx`

**Interfaces:**
- Produces: `ANALYTICS_QUERY.query` gains `placeholderData: keepPreviousData`. `QueryGate`'s `query` prop gains `isPlaceholderData?: boolean`; when true, children render inside a wrapper with `aria-busy="true"` and `opacity-60 transition-opacity` (the same wrapper with `aria-busy="false"` and no dimming otherwise, so the layout does not change).

- [ ] **Step 1: Write the failing tests** in `query-gate.test.tsx`: `dims and marks busy while placeholder data shows` (`data` set, `isPlaceholderData: true` → children's wrapper has `aria-busy="true"`); `a first load still shows the skeleton` (`data: undefined`, `isPlaceholderData: false` → skeleton) — Review Focus 5.
- [ ] **Step 2: Run; confirm the first fails.**
- [ ] **Step 3: Implement**; check every tab passes its query object straight to `QueryGate` (so `isPlaceholderData` arrives); `grep` that nothing imports `ANALYTICS_STALE_TIME` from `home-dashboard`.
- [ ] **Step 4: `make check-web`, `make test-web` — PASS.**
- [ ] **Step 5: Commit** — `Web: analytics keeps the old period's figures, dimmed, while a new one loads`.

---

### Task 9: Flow tab skeleton without the shift

**Files:**
- Modify: `web-app/apps/web/src/components/analytics/flow-tab.tsx` (the `skeleton` prop)
- Test: `flow-tab.test.tsx`

- [ ] **Step 1: Measure** the rendered heights of the month-to-date strip and the latest-month section in the running app (this worktree's web is http://localhost:3010; start it via the `/run-stack` skill if not up) at mobile and desktop widths. Record them in the step's commit body.
- [ ] **Step 2: Write the failing tests:** the loading skeleton has a strip block (`data-testid="mtd-skeleton"`) and a latest-month block (`data-testid="latest-skeleton"`) in their real order (strip first, latest after Cash flow, as rendered); with a cached dashboard whose `reference_partial` is true, the strip block is absent.
- [ ] **Step 3: Implement**: skeleton blocks with the measured heights (`Skeleton` with fixed `h-*`, responsive if the heights differ). For "the period is the month in progress" before any spending data, read the dashboard query's cached data (`queryClient.getQueryData` for the dashboard key, via the generated query-key helper) and hide the strip block when `reference_partial`; with nothing cached, show it.
- [ ] **Step 4: Verify in the browser** that loading the Flow tab (hard reload, throttled network) no longer shifts the Income and expenses section; `make test-web` — PASS.
- [ ] **Step 5: Commit** — `Web: the Flow tab's skeleton holds the strip and latest-month blocks`.

---

### Task 10: url-state exports; `/analytics` on nuqs

**Files:**
- Modify: `web-app/packages/data-table/src/url-state/params.ts` (add `parseAsNumberLiteral` and `useQueryStates` to the nuqs re-export)
- Modify: `web-app/apps/web/src/components/analytics/use-analytics-params.ts`
- Test: `web-app/apps/web/src/components/analytics/use-analytics-params.test.ts`

**Interfaces:**
- `useAnalyticsParams()` keeps its return shape exactly: `{ tab, setTab(next), months(forTab), setMonths(forTab, value) }`, and `ANALYTICS_TABS`, `PERIODS`, `isAnalyticsTab` stay exported.

- [ ] **Step 1: Port the test to nuqs**: replace the `next/navigation` mock and `replaceState` spy with `withNuqsTestingAdapter` from `@app/data-table/url-state/testing`, asserting URL updates via its `onUrlUpdate`. Keep every existing case (unknown tab → default, out-of-choice months → fallback, the default value removes the key, writes replace rather than push and are shallow). Run against the old hook: cases asserting on URL writes fail.
- [ ] **Step 2: Rewrite the hook** with `useQueryStates` over `tab: parseAsStringLiteral(ANALYTICS_TABS).withDefault("category")` and each `PERIODS[*].key: parseAsNumberLiteral(choices).withDefault(fallback)`, options `{ history: "replace", shallow: true, clearOnDefault: true }`. Confirm the app's layout already mounts the nuqs adapter (the transactions table uses it).
- [ ] **Step 3: Run the test, `analytics-page.test.tsx`, then `make check-web`, `make test-web` — PASS.** Check in the browser that switching tab and period updates the URL without a page fetch.
- [ ] **Step 4: Commit** — `Web: /analytics keeps its tab and periods through the url-state package`.

---

### Task 11: Shared chart props

**Files:**
- Modify: `web-app/apps/web/src/components/dashboard/trend-chart.tsx`; possibly `web-app/apps/web/src/components/analytics/chart-parts.tsx`

**Interfaces:**
- Consumes: `MARGIN`, `GRID`, `X_AXIS`, `MONEY_Y_AXIS`, `LINE_TOOLTIP` from `components/analytics/chart-parts.tsx` — whichever are identical in intent to `trend-chart.tsx`'s own literals.

- [ ] **Step 1: Diff** `trend-chart.tsx`'s chart props against `chart-parts.tsx`; list which are identical and which differ on purpose (e.g. a different tick formatter for the dashboard).
- [ ] **Step 2: Replace the identical ones** with the shared constants. If `chart-parts.tsx` imports anything that would pull analytics components into the home bundle, move the constants it shares into a plain module first. Leave the purposeful differences, with a one-line comment why.
- [ ] **Step 3: `make check-web`, `make test-web` — PASS; look at the home dashboard trend chart in the browser — unchanged.**
- [ ] **Step 4: Commit** — `Web: the dashboard trend chart uses the analytics chart props`.

---

### Task 12: Server-status ring

**Files:**
- Modify: `web-app/packages/components/src/settings/server-status-indicator.tsx` (the ring at ~line 66)
- Test: `web-app/packages/components/src/settings/server-status-indicator.test.tsx`

- [ ] **Step 1: Write the failing test** `no pulsing ring when a healthy status is stale behind an error`: `status={{ status: "healthy" }}`, `error={new Error("down")}`, `isLoading={false}` → the dot is red (`bg-red-500`) and no element has `animate-ping`.
- [ ] **Step 2: Run; confirm it fails.**
- [ ] **Step 3: Gate the ring** on `!error && status?.status === "healthy"` — the same condition as green.
- [ ] **Step 4: Run the file, `make test-web` — PASS.**
- [ ] **Step 5: Commit** — `Web: the status dot stops pulsing when it shows an error`.

---

### Task 13: `QueryProvider` retry and quiet-refetch tests

**Files:**
- Test: `web-app/packages/api-client/src/query-provider.test.tsx`

- [ ] **Step 1: Write the tests** (reuse the file's `FailingQuery` pattern; count `queryFn` calls; use `waitFor` with a timeout above TanStack's default 1 s retry delay, or fake timers):
  - `does not retry a 4xx`: a query rejecting `new ApiError(...)` with status 404 → `queryFn` called once.
  - `retries a 5xx once`: status 500 → called twice, then the error toasts once.
  - `a failed refetch behind data already shown does not toast`: first call resolves, `refetch()` rejects with 500 (twice, through the retry) → `toastForError` never called.
- [ ] **Step 2: Run** — expected PASS against the current code. **If any fails, stop and report to the user** with the output; do not change `query-provider.tsx`.
- [ ] **Step 3: Commit** — `Web: tests for QueryProvider's retry rule and the quiet refetch`.

---

### Task 14: Docs

**Files:**
- Modify: `docs/product/features/analytics.md` §3 (averaging bullet and the burn-rate bullet: null when the period has no whole month; the month-to-date bullet: `previous_through` and `net` come from the server)
- Modify: `docs/architecture/server.md` or wherever analytics' service layer is described (find it with `grep -rn "AnalyticsService\|analytics_service" docs/`): `AnalyticsHistory` — load once, compute any window; the caller for step 7
- Modify: `docs/TODO.md` — delete the closed **Wave 3 cleanup** bullets (keep only "Promote `Section`, `Change` and `PeriodSelect`…", moved under a heading that does not name this step, e.g. **Web — analytics page parts**); delete the QueryProvider bullet from **Web — tests**; repoint the row-cache entry's "After: the Wave 3 cleanup" to `AnalyticsHistory`
- Modify: `docs/BUGS.md` — delete the two entries this step fixed

- [ ] **Step 1: Make the edits.**
- [ ] **Step 2: `grep -rn "_usual_months\|_same_days_previous_month\|ANALYTICS_STALE_TIME.*home-dashboard" docs server web-app/apps` — nothing left.**
- [ ] **Step 3: Commit** — `Docs: wave 3 cleanup — the averaging rule, AnalyticsHistory; closed TODO and BUGS entries`.

The roadmap row, deleting this plan and the spec, and the PR are `superpowers:finishing-a-development-branch`'s, per `.superpowers/BRIEF.md` §4.
