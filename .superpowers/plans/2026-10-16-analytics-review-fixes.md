# Analytics page review fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the code-review findings on PR #17 (the `/analytics` page) before merge: one loading/error/empty state per request, shared chart setup, a URL write without a server round trip, and four smaller fixes.

**Architecture:** Every change stays inside `web-app/apps/web/src/components/analytics/` (plus one sentence in `docs/product/features/analytics.md`). A new `QueryGate` owns a request's error and empty states at tab level; `Section` becomes a plain titled card. Chart props move into one shared module, and the two month-point mappers merge into one.

**Tech Stack:** Next.js 16.2.3 App Router, React, TanStack Query (orval hooks from `@app/api-client`), recharts via `@app/ui/chart`, Vitest + Testing Library.

**Spec:** No separate spec file. The authority is the code review of PR #17 (2026-10-16) and the user's decisions, recorded verbatim under **Decisions** below. The page's product rules are in `docs/product/features/analytics.md` §2, which still binds.

## Decisions (from the user, 2026-10-16)

- Fix review items 1–5 and M2; do M1 too: **one error per request**, not one per card.
- Loading keeps a skeleton per card (layout must not jump); only the error and empty states become one per request.
- An error with nothing loaded yet shows one `SectionError` ("Couldn't load …" + Retry) in place of every card that request feeds. Once data has loaded, a failed background refetch keeps showing it (unchanged).
- Resulting maxima: Income vs Expenses 1, Seasonality 1, By Category 2 (categories, merchants), Trends 2 (spending, category movers). On By Category the "Total spent / compared with" header is under the categories request.
- "Needs at least two whole months." shows only when **both** movers lists are empty (one empty state for the movers request). A single empty list reads "No category grew/declined between the two halves of the period." with no hint. Accepted cost: a period in which no category changed at all also shows the hint.
- The four out-of-ownership follow-ups (url-state exports in `@app/data-table`, moving `ANALYTICS_STALE_TIME`, sharing chart props with `dashboard/trend-chart.tsx`, promoting to `@app/ui`) are **not** in this plan; the orchestrator holds them for after the wave.

## Global Constraints

- Edit only `web-app/apps/web/src/components/analytics/` and `docs/product/features/analytics.md`. Read-only: `components/dashboard/` (imports `SectionError`, `ANALYTICS_STALE_TIME`, `formatMonth` allowed), `server/`, `packages/api-client/src/generated/`, `@app/ui`, `@app/core`. Importing from `@app/core/lib/dates` is allowed.
- The server computes every figure; the page formats only. No new arithmetic on money or percents. `Math.abs` for display is allowed (already used).
- Labels come from the server's dates, never the browser clock: no `new Date()` without arguments, no `Date.now`, no `toISOString`.
- A null percent reads "—" or a short reason, never 0.
- Colour means good or bad and always comes with an arrow or words. Every colour is a theme token.
- Commit messages start with `Analytics page: `.
- After each task: `cd web-app/apps/web && pnpm vitest run src/components/analytics` passes, and `make check-web` (from the repo root) is clean.

## Review Focus

1. **A refetch that fails after data loaded:** the cards keep showing data and no error card appears. Pinned in Task 1 (`QueryGate` test "keeps data when a refetch fails").
2. **An empty Trends tab for a user with no data:** the movers request is empty with `date_from === null`. It must read "No transactions in this period.", not the two-whole-months hint. Pinned in Task 1 (trends-tab test).
3. **A tab or period click must update the view without `router.replace`:** `useSearchParams` must re-read after `window.history.replaceState`. Unit tests mock `next/navigation`, so only the browser pass proves it. Pinned in Task 4.
4. **A savings rate of exactly 0:** it reads "Kept 0.0% of income" in the neutral tone, not "Spent 0.0% more". Pinned in Task 3.
5. **Weekday order and names:** `weekday` 0 is Monday (generated type comment). Seven points must stay in the server's order, with names from `Intl` in the browser locale. Pinned in Task 3.

---

### Task 1: One loading, error and empty state per request (M1, review fix 2)

**Files:**
- Create: `query-gate.tsx`, `query-gate.test.tsx`
- Modify: `section.tsx`, `flow-tab.tsx`, `trends-tab.tsx`, `seasonality-tab.tsx`, `category-tab.tsx`, `top-merchants.tsx`, `category-movers.tsx`, `shared.test.tsx` (drop its `Section` tests, which move to `query-gate.test.tsx`), and the four tab test files
- Modify: `docs/product/features/analytics.md:81-82`

**Interfaces:**
- Produces:
  - `Section({ title, children }: { title: string; children: ReactNode })`: a plain `Card` with a `CardHeader`/`CardTitle` and `CardContent`. No query logic.
  - `QueryGate<T>({ query, what, skeleton, isEmpty, empty, children })` in `query-gate.tsx`, where:
    - `query: { data: T | undefined; isError: boolean; refetch: () => unknown }`
    - `what: string`
    - `skeleton: ReactNode`
    - `isEmpty: (data: T) => boolean`
    - `empty: ReactNode | ((data: T) => ReactNode)`
    - `children: (data: T) => ReactNode`
  - `QueryGate` renders:
    - nothing loaded and `isError`: one `<SectionError what={what} onRetry={() => void refetch()} />`;
    - nothing loaded, no error: `skeleton`;
    - `isEmpty(data)`: one untitled `Card` whose `CardContent` holds the empty node, as `text-sm text-muted-foreground`;
    - otherwise: `children(data)`.

- [ ] **Step 1: Write `query-gate.test.tsx`.** Port the `Section` cases from `shared.test.tsx` and assert:
  - skeleton while `data` is undefined and there is no error;
  - exactly one "Couldn't load things." and one Retry when `data` is undefined and `isError`;
  - Retry calls `refetch`;
  - children render, with no "Couldn't load", when `data` is set and `isError` is true;
  - the empty node renders once when `isEmpty` is true;
  - a function `empty` receives the data.
- [ ] **Step 2: Run it and see it fail** (module missing).
- [ ] **Step 3: Implement `QueryGate`, and reduce `Section` to the plain titled card.**
- [ ] **Step 4: Move each tab onto one gate per request.**
  - **Each tab:**
    - The `PeriodSelect` and period-line header stays outside the gate.
    - The gate's `skeleton` is a fragment of the titled `Section`s that request feeds, each holding its current `Skeleton`, so the layout doesn't jump.
    - Inside `children`, the same titled `Section`s render the content.
  - **`flow-tab.tsx`:**
    - One gate for `useGetSpending`, `what` "your income and expenses".
    - The month-to-date strip moves inside the gate's children.
    - The latest-month card renders when `d.latest_month` is set, read once into a local constant. No `!` remains.
    - Delete the `section` prop bag.
  - **`category-tab.tsx`:**
    - One gate for the categories request.
    - Its children render the "Total spent / compared with" block, the ranking card and the "How often vs how much" card.
    - Delete `hasSpending` and the prop bag. `isEmpty` is unchanged.
  - **`top-merchants.tsx`:** its own gate. The skeleton is a titled "Top merchants" `Section` with the current `Skeleton`. The empty text is unchanged.
  - **`trends-tab.tsx`:**
    - A spending gate covers the three charts.
    - A movers gate covers Growing and Declining.
      - Movers `isEmpty`: `d.date_from === null || (d.top_growing.length === 0 && d.top_declining.length === 0)`.
      - Movers `empty`: when `d.date_from === null`, "No transactions in this period."; otherwise two lines, "No category grew or declined between the two halves of the period." and the smaller `text-xs` "Needs at least two whole months.".
  - **`category-movers.tsx`:** an empty `rows` renders only the `empty` sentence. The "Needs at least two whole months." line goes.
  - **`seasonality-tab.tsx`:** one gate for `useGetBehaviour`, covering the three cards, with the empty text "No spending yet.".
- [ ] **Step 5: Change the tab tests to exact counts.**
  - **`flow-tab.test.tsx:251`:** `getAllByText(/Couldn't load your income and expenses/)` has length 1.
  - **`trends-tab.test.tsx`:**
    - At `:247/:250`, each "Couldn't load" has length 1.
    - At `:215`, rewrite the case so both lists are empty with a non-null `date_from`: "Needs at least two whole months." appears once.
    - Add a case where only `top_growing` is empty: "No category grew between the two halves of the period." shows and the hint is absent.
    - Add a case where `date_from` is null: "No transactions in this period." shows and the hint is absent.
  - **`seasonality-tab.test.tsx:162`:** "No spending yet." has length 1.
  - **`category-tab.test.tsx:172`:** "No spending in this period." has length 1.
- [ ] **Step 6: Edit `analytics.md:81-82`.** It should read: "Every chart has a loading skeleton. Each request has one empty state and fails on its own: one error card with a retry, in place of the charts that request feeds, without taking the page down."
- [ ] **Step 7: Run the analytics tests and `make check-web`.** Both pass.
- [ ] **Step 8: Commit** `Analytics page: one error and empty state per request, not per card`.

### Task 2: Shared chart parts and one month-point mapper (M2)

**Files:**
- Create: `chart-parts.tsx` (replaces `chart-tooltip.ts`, which is deleted), `month-points.ts`, `month-points.test.ts`
- Delete: `flow-points.ts`, `flow-points.test.ts`, `trends-points.ts`, `trends-points.test.ts` (their cases move to `month-points.test.ts`)
- Modify: `flow-chart.tsx`, `trends-charts.tsx`, `seasonality-charts.tsx`, `flow-tab.tsx`, `trends-tab.tsx`

**Interfaces:**
- Produces, in `chart-parts.tsx`:
  - `MARGIN = { left: 4, right: 8, top: 8 }`
  - `GRID = { vertical: false, strokeDasharray: "3 3" }`
  - `X_AXIS = { dataKey: "label", tickLine: false, axisLine: false, tickMargin: 8 }`
  - `MONEY_Y_AXIS` and `PCT_Y_AXIS`: `{ tickLine: false, axisLine: false, width: 48, tickFormatter }`, the compact number formatter and `` `${v}%` `` respectively.
  - `BAR_TOOLTIP` and `LINE_TOOLTIP`, unchanged from `chart-tooltip.ts`, keeping their doc comment.
  - `partialOpacity(p: { partial: boolean }) => 0.4 | 1`
  - `monthTooltipLabel(p: MonthPoint | undefined) => string | undefined`: "Oct 2026", with " (so far)" or " (partial)" appended.
  - `TooltipBox({ children })`: a `div` with the primitive's class `rounded-lg border bg-popover px-2.5 py-1.5 text-xs text-popover-foreground shadow-md` (from `packages/ui/src/primitives/chart.tsx:92`, minus its grid and min-width).
  - All are spread as props (`<CartesianGrid {...GRID} />`), which is the pattern `BAR_TOOLTIP` already uses.
- Produces, in `month-points.ts`:
  - `type MonthPoint = { month; label; partial; partialLabel; income: number; expenses: number; rollingAvg: number | null; change: number | null; savingsRate: number | null }`
  - `toMonthPoints(months: MonthFlowResponse[], currentMonth?: string | null): MonthPoint[]`, the superset of today's `toFlowPoints` and `toTrendsPoints` fields, with the same conversions.
  - `monthToDate(data: SpendingResponse): MonthToDateResponse | null` replaces the boolean `showMonthToDate`. It returns the strip to show, or null under the same rule.

- [ ] **Step 1: Write `month-points.test.ts`.** Merge every case from `flow-points.test.ts` and `trends-points.test.ts`. The `showMonthToDate` cases now assert on `monthToDate`, which returns the `month_to_date` object or `null`.
- [ ] **Step 2: Run it and see it fail.**
- [ ] **Step 3: Implement `month-points.ts` and `chart-parts.tsx`. Delete the old point files and `chart-tooltip.ts`.**
- [ ] **Step 4: Rewrite the six charts on `chart-parts`.**
  - No chart file keeps its own `compact`, `MARGIN`, `TIP` class, `monthLabel` or `Cell` opacity expression.
  - Charts take `MonthPoint[]`.
  - `SpendingTrendChart` uses `BAR_TOOLTIP`; it draws bars, so the band cursor fits.
  - The two hand-built tooltips in `trends-charts.tsx` and the two in `seasonality-charts.tsx` use `TooltipBox`.
  - The weekday chart's X axis keeps its own `dataKey` and tick formatter until Task 3 gives `WeekdayPoint` a `label`.
- [ ] **Step 5: Build the points once per tab.**
  - In `trends-tab.tsx`, inside the spending gate's children: `const points = toMonthPoints(d.months, d.month_to_date?.month)`, passed to all three charts.
  - In `flow-tab.tsx`: `const mtd = monthToDate(d)`, and render the strip from `mtd`. No `!`.
- [ ] **Step 6: Run the analytics tests and `make check-web`.** Both pass.
- [ ] **Step 7: Commit** `Analytics page: shared chart parts and one month-point mapper`.

### Task 3: Savings wording, local weekday names, and small fixes (review fixes 3, 4, 5)

**Files:**
- Modify: `change.tsx`, `flow-tab.tsx`, `trends-tab.tsx`, `seasonality-points.ts`, `seasonality-points.test.ts`, `seasonality-charts.tsx`, `seasonality-tab.tsx`, `format.ts`, `format.test.ts`, `month-to-date-strip.tsx`, `analytics-page.tsx`, `analytics-page.test.tsx`, `use-analytics-params.ts`, `flow-tab.test.tsx`, `trends-tab.test.tsx`

**Interfaces:**
- Produces:
  - `SavingsHeadline({ pct }: { pct: number | null })` in `change.tsx`:
    - `null` reads "—";
    - `pct >= 0` reads `` `Kept ${formatPct(pct)} of income` ``;
    - `pct < 0` reads `` `Spent ${formatPct(Math.abs(pct))} more than income` ``;
    - it wraps a `<span data-tone className={TONE_CLASS[tone]}>` with `tone = changeTone(pct, "income")`.

    It replaces `Kept` in `flow-tab.tsx` and the inline headline in `trends-tab.tsx`. The table's `Rate` stays a signed percent.
  - `WeekdayPoint` gains `label: string` (short weekday, e.g. "Mon") and its `name` becomes the long weekday from `Intl`. Both come from `Intl.DateTimeFormat(undefined, { weekday })` on `new Date(2024, 0, 1 + d.weekday)`; 1 Jan 2024 was a Monday, and `weekday` 0 is Monday.
  - `isAnalyticsTab(v: unknown): v is AnalyticsTab`, exported from `use-analytics-params.ts`.

- [ ] **Step 1: Write the failing tests.**
  - **Savings wording, in the Flow "Cash flow" card and the Trends "Savings rate" card:**
    - pct −6.5 reads "Spent 6.5% more than income" (via `formatPct(6.5)`) with `data-tone="bad"`;
    - pct 0 reads "Kept 0.0% of income" with `data-tone="neutral"`;
    - pct 33.1 reads "Kept 33.1% of income".
  - **`seasonality-points.test.ts`:** the points keep the server's order. `weekday` 0 gives the label and name `Intl` produces for 1 Jan 2024, computed in the test the same way, not hard-coded "Monday".
  - **`format.test.ts`:** `formatPeriod("2026-02-30", "2026-03-31")` returns `null`, since an invalid day no longer becomes 2 March.
  - **`analytics-page.test.tsx`:** selecting a tab writes the URL.
- [ ] **Step 2: Run them and see them fail.**
- [ ] **Step 3: Implement.**
  - `SavingsHeadline`, used in both tabs.
  - Weekday labels:
    - `WeekdayChart` and the Seasonality table use `X_AXIS`, with `label` on the axis and `name` in the tooltip and table.
    - Drop the `.slice(0, 3)` tick formatter.
  - In `format.ts`, replace the local `parseDate` with `parseIsoDay` from `@app/core/lib/dates`; `formatPeriod` returns `null` if either end fails to parse.
  - In `month-to-date-strip.tsx`, read the day as `parseIsoDay(data.through)?.getDate()`. If it is undefined, render the strip without the day ranges rather than throwing.
  - In `analytics-page.tsx`, `onValueChange={(v) => { if (isAnalyticsTab(v)) setTab(v) }}`, and `useAnalyticsParams` uses `isAnalyticsTab` for its own parse.
- [ ] **Step 4: Run the analytics tests and `make check-web`.** Both pass.
- [ ] **Step 5: Commit** `Analytics page: savings wording for a negative rate, weekday names in the browser's language, date parsing via parseIsoDay`.

### Task 4: URL writes without a server round trip (review fix 1), then the browser pass

**Files:**
- Modify: `use-analytics-params.ts`, `use-analytics-params.test.ts`, `analytics-page.test.tsx`

**Interfaces:**
- Consumes: `useAnalyticsParams()`; its return shape is unchanged.
- Changes: `write()` calls `window.history.replaceState(null, "", url)` instead of `router.replace(url, { scroll: false })`, and `useRouter` is no longer imported. The URL string is built exactly as today. Next 16 syncs `useSearchParams` with `history.replaceState` (`node_modules/next/dist/docs/01-app/02-guides/single-page-applications.md:300-302`); read that passage to confirm before relying on it.

- [ ] **Step 1: Retarget the tests.**
  - Replace the `useRouter` mock with `vi.spyOn(window.history, "replaceState")`.
  - Assert on the URL argument, e.g. `expect(spy).toHaveBeenCalledWith(null, "", "/analytics?tab=flow&trend_months=12&flow_months=12")`, and `"/analytics"` when every value is a default.
  - The tests in `analytics-page.test.tsx` that assert a tab click writes the URL get the same change.
- [ ] **Step 2: Run them and see them fail. Then implement, run them and see them pass.**
- [ ] **Step 3: Run the full suite (`make test-web`), `make check-web`, and `pnpm build` in `web-app/apps/web`.** All pass.
- [ ] **Step 4: Commit** `Analytics page: write the tab and period to the URL without a server round trip`.
- [ ] **Step 5: Do a browser pass on the slot-1 stack** (web 3010, API 8110), as the seeded user and as an empty user, at desktop and 375 px, in light and dark. Confirm:
  - A tab or period click switches at once, and the network panel shows no RSC (`?_rsc=`) request for it. A reload keeps the tab and period, and Back still leaves `/analytics`, as before.
  - One failing request per tab, forced with Playwright `page.route(…, r => r.abort())` on that endpoint, shows exactly one "Couldn't load …" card per failing request, and Retry recovers.
  - Empty user: one empty card per request, and Trends' movers read "No transactions in this period.".
  - The chart tooltips use the popover colours in dark mode, and the partial month is still lighter.
  - Seasonality weekday names appear on the axis, in the table and in the tooltip.

  Any defect found is fixed and committed with the `Analytics page: ` prefix.

### Task 5: Close out

- [ ] **Step 1: Delete this plan file** (repo convention: its lasting facts are the `analytics.md` sentence from Task 1). Commit `Analytics page: review-fix plan removed`.
- [ ] **Step 2: Push to `feat/analytics-page`** (pre-push runs the web checks). Comment on PR #17 with the list of review fixes, then message `orchestrator` with the new head commit.
