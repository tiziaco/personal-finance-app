---
phase: 02-dashboard
plan: 04
subsystem: ui
tags: [react, nextjs, tanstack-query, shadcn, base-ui, dashboard, insights, transactions]

# Dependency graph
requires:
  - phase: 02-dashboard plan 01
    provides: DashboardResponse type narrowing, format utilities (formatCurrency, formatDate)
  - phase: 01-foundation
    provides: useTransactions hook, useInsights hook, TransactionResponse, InsightsResponse types, skeleton components

provides:
  - RecentTransactions widget — last 10 transactions with merchant/date/amount/category, View All link to /transactions
  - InsightsCallout widget — top 2 AI insights, stale-data "New data" badge, Generate New Insights + Upload CSV CTAs

affects: [03-transactions, 05-insights, dashboard-page-assembly]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "buttonVariants + Link pattern for navigation buttons (base-ui Button has no asChild prop)"
    - "filters.limit override pattern in useTransactions for variable-page-size callers"
    - "Dual useTransactions call in InsightsCallout — limit:1 for freshness check, separate cache key from limit:10 RecentTransactions"

key-files:
  created:
    - web-app/src/components/dashboard/recent-transactions.tsx
    - web-app/src/components/dashboard/insights-callout.tsx
  modified:
    - web-app/src/hooks/use-transactions.ts

key-decisions:
  - "buttonVariants + Link instead of Button asChild — @base-ui/react/button does not expose asChild; buttonVariants exported for standalone styling"
  - "filters.limit ?? 25 in useTransactions — filters spread was overwritten by hardcoded limit=25; fix enables dashboard widgets to request exactly 10 (or 1) rows"
  - "InsightsCallout uses two separate useTransactions calls: limit:1 for stale-data badge (cheap check) vs limit:10 for RecentTransactions (separate React Query cache key)"

patterns-established:
  - "buttonVariants + Link: for all navigation buttons in base-ui-based app, use cn(buttonVariants({ variant, size })) on next/link instead of Button asChild"

requirements-completed: [DASH-05, DASH-06, DASH-07, DASH-08]

# Metrics
duration: 3min
completed: 2026-02-27
---

# Phase 2 Plan 04: RecentTransactions and InsightsCallout Dashboard Widgets Summary

**RecentTransactions widget (limit:10, View All link) and InsightsCallout (top 2 AI insights, stale "New data" badge, Generate New Insights + Upload CSV CTAs) completing the five-section dashboard**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-02-27T12:54:29Z
- **Completed:** 2026-02-27T12:57:17Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Built `RecentTransactions` — calls `useTransactions({ limit: 10 })`, renders merchant/date/category badge/amount rows, "View All" link to /transactions, empty state with Upload CSV
- Built `InsightsCallout` — calls `useInsights()` + `useTransactions({ limit: 1 })`, shows top 2 insight summaries, displays "New data" badge (destructive) in CardHeader when latest transaction date is newer than `generated_at`, has "Generate New Insights" in both empty and non-empty states, "Upload CSV" to /upload
- Fixed `useTransactions` hook bug — filters.limit was being silently overridden by hardcoded `limit = 25` in the spread; changed to `filters.limit ?? 25`

## Task Commits

Each task was committed atomically:

1. **Task 1: RecentTransactions widget (DASH-05)** - `2dccab1` (feat)
2. **Task 2: InsightsCallout widget (DASH-06/07/08)** - `0abd007` (feat)

## Files Created/Modified

- `web-app/src/components/dashboard/recent-transactions.tsx` — Last-10-transactions widget with merchant/date/category badge/amount, View All → link, empty state CTA
- `web-app/src/components/dashboard/insights-callout.tsx` — AI insights widget with top 2 summaries, stale-data badge, Generate New Insights + Upload CSV CTAs
- `web-app/src/hooks/use-transactions.ts` — Bug fix: `filters.limit ?? 25` so callers can override page size

## Decisions Made

- **buttonVariants + Link pattern:** `@base-ui/react/button` does not support `asChild` (Radix UI pattern). Used `cn(buttonVariants({ variant, size }))` on `next/link` directly — consistent with base-ui's `render` prop philosophy but simpler for navigation-only links.
- **filters.limit override fix:** The hook spread was `{ ...filters, offset, limit }` where `limit = 25` always overwrote `filters.limit`. Changed to `filters.limit ?? 25` so dashboard widgets can request 1 or 10 rows without duplicating hook logic.
- **Separate React Query cache keys:** `useTransactions({ limit: 1 })` and `useTransactions({ limit: 10 })` produce different query keys — no cache collision or over-fetching.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed useTransactions limit override**
- **Found during:** Task 1 (RecentTransactions widget creation)
- **Issue:** `useTransactions` hook spread `{ ...filters, offset, limit }` where `limit = 25` always overwrote `filters.limit`. Passing `limit: 10` in filters had no effect — 25 rows would always be fetched and rendered.
- **Fix:** Changed `const limit = 25` to `const limit = filters.limit ?? 25` in the hook. Offset calculation uses the effective limit.
- **Files modified:** `web-app/src/hooks/use-transactions.ts`
- **Verification:** TypeScript clean compile (0 errors). Plan's intended behavior of passing `limit: 10` now works correctly.
- **Committed in:** `2dccab1` (Task 1 commit)

**2. [Rule 1 - Bug] Replaced Button asChild with buttonVariants + Link**
- **Found during:** Task 1 (initial TypeScript check)
- **Issue:** Plan used `<Button asChild>` pattern, but the project's `Button` is built on `@base-ui/react/button` which doesn't have `asChild` (that's a Radix UI primitive feature). TypeScript reported type error on the `asChild` prop.
- **Fix:** Used `cn(buttonVariants({ variant, size }))` directly on `next/link` — semantically equivalent, correctly typed, consistent with base-ui's design.
- **Files modified:** `web-app/src/components/dashboard/recent-transactions.tsx`, `web-app/src/components/dashboard/insights-callout.tsx`
- **Verification:** TypeScript reports 0 errors (`tsc exit:0`).
- **Committed in:** `2dccab1` and `0abd007`

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bugs)
**Impact on plan:** Both fixes necessary for correctness. The limit fix ensures widgets fetch and display the correct number of rows. The buttonVariants fix resolves the type error from the plan's incorrect assumption about `asChild` support. No scope creep.

## Issues Encountered

None beyond the two auto-fixed deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Dashboard section widgets are now complete: WelcomeCard, SummaryCards, SpendingPieChart, TrendLineChart (Plans 02-03), RecentTransactions, InsightsCallout (Plan 04)
- Dashboard page assembly (Plan 05) can import all six widgets
- Phase 3 (Transactions) will build the `/transactions` page that RecentTransactions' "View All" link points to
- Phase 5 (Insights) will build the `/stats` page that InsightsCallout's CTAs link to
- `/upload` route is still a stub (404 acceptable per plan routing note)

---
*Phase: 02-dashboard*
*Completed: 2026-02-27*
