---
phase: 01-foundation
plan: 05
subsystem: ui
tags: [react-query, tanstack-query, clerk, hooks, typescript]

# Dependency graph
requires:
  - phase: 01-foundation plan 03
    provides: API functions (fetchTransactions, fetchDashboard, fetchSpendingAnalytics, etc.)
  - phase: 01-foundation plan 01
    provides: TypeScript types (TransactionFilters, AnalyticsFilters, InsightsResponse, CATEGORY_OPTIONS)
provides:
  - useTransactions(filters, page) — paginated + filtered transaction query with keepPreviousData
  - useCategories() — static CATEGORY_OPTIONS, zero API calls
  - useDashboardSummary(filters) — dashboard query with 2-minute staleTime
  - useSpendingAnalytics, useCategoriesAnalytics, useMerchantsAnalytics, useRecurringAnalytics, useBehaviorAnalytics, useAnomaliesAnalytics — each with enabled flag for lazy tab loading
  - useInsights() — insights query with staleTime=10min and gcTime=30min
affects: [Phase 2 dashboard, Phase 3 transactions, Phase 4 analytics, Phase 5 insights]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "React Query v5 hooks: token retrieved inside queryFn via await getToken()"
    - "placeholderData: keepPreviousData for pagination (v5 import syntax)"
    - "enabled flag pattern for tab-based lazy loading in analytics hooks"
    - "useCategories returns static array directly — no useQuery needed when there is no API endpoint"

key-files:
  created:
    - web-app/src/hooks/use-transactions.ts
    - web-app/src/hooks/use-categories.ts
    - web-app/src/hooks/use-dashboard-summary.ts
    - web-app/src/hooks/use-analytics.ts
    - web-app/src/hooks/use-insights.ts
  modified: []

key-decisions:
  - "getToken() called inside queryFn (not hook body) — token is not stable and should not be in queryKey or hook scope"
  - "useCategories returns CATEGORY_OPTIONS statically — no /categories endpoint exists on backend"
  - "Analytics hooks accept enabled=true flag — supports Phase 4 tab-based lazy loading without refactoring"
  - "staleTime ladder: transactions=30s, dashboard=2min, analytics=5min, insights=10min — proportional to compute cost"

patterns-established:
  - "Token pattern: const { getToken } = useAuth() in hook body; const token = await getToken() inside queryFn"
  - "All hooks with useAuth have 'use client' directive; pure static hooks omit it"
  - "No hook imports fetch() directly — all delegate to API functions from lib/api/"
  - "Analytics hooks use shared ANALYTICS_STALE_TIME constant to keep staleTime consistent"

requirements-completed: [FOUND-03]

# Metrics
duration: 1min
completed: 2026-02-27
---

# Phase 1 Plan 05: React Query Data Hooks Summary

**Five typed React Query hooks wiring Clerk token retrieval to all API endpoints — transactions, categories, dashboard, 6 analytics variants, and insights with stale-while-revalidate caching strategy.**

## Performance

- **Duration:** 1 min
- **Started:** 2026-02-27T06:44:45Z
- **Completed:** 2026-02-27T06:45:51Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- useTransactions with `placeholderData: keepPreviousData` (React Query v5 import syntax), 30s staleTime, pagination via offset/limit
- useCategories returning CATEGORY_OPTIONS statically with zero API calls and zero React Query overhead
- useDashboardSummary, 6 analytics hooks (each with `enabled` flag), and useInsights with 10min staleTime + 30min gcTime
- Consistent token pattern: `getToken()` called inside `queryFn`, never in hook body or component scope

## Task Commits

Each task was committed atomically:

1. **Task 1: Create transaction, categories, and dashboard hooks** - `f8deb35` (feat)
2. **Task 2: Create analytics and insights hooks** - `de7a15e` (feat)

## Files Created/Modified

- `web-app/src/hooks/use-transactions.ts` — paginated transaction query with keepPreviousData (v5), staleTime 30s
- `web-app/src/hooks/use-categories.ts` — static CATEGORY_OPTIONS return, no useQuery or API call
- `web-app/src/hooks/use-dashboard-summary.ts` — dashboard query, staleTime 2 minutes
- `web-app/src/hooks/use-analytics.ts` — 6 analytics hooks with enabled flag and staleTime 5 minutes
- `web-app/src/hooks/use-insights.ts` — insights query, staleTime 10 minutes, gcTime 30 minutes

## Decisions Made

- `getToken()` is called inside `queryFn` because the token is not stable across renders and should not appear in the `queryKey`; this is the correct Clerk + React Query integration pattern
- `useCategories` intentionally omits `useQuery` — there is no `/categories` backend endpoint; returning a static array is simpler and avoids unnecessary cache entries
- All analytics hooks accept `enabled = true` to support Phase 4 tab-based lazy loading (tabs set `enabled: false` until activated)
- staleTime values are proportional to compute cost: transactions mutate on upload (30s); dashboard is aggregated (2min); analytics are expensive server computations (5min); insights involve AI generation (10min)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Phase 1 Complete — All Foundation Deliverables

The full Phase 1 foundation layer is now complete:

| Plan | Deliverable |
|------|-------------|
| 01   | TypeScript types: TransactionResponse, AnalyticsResponse, InsightsResponse, CATEGORY_OPTIONS |
| 02   | Shared UI primitives: SkeletonCard, SkeletonTable, ErrorBoundary |
| 03   | API client layer: fetchTransactions, fetchDashboard, all analytics + insights functions |
| 04   | Chart wrapper components: BarChartWrapper, LineChartWrapper, PieChartWrapper, AreaChartWrapper |
| 05   | React Query hooks: useTransactions, useCategories, useDashboardSummary, 6 analytics hooks, useInsights |

Pages and components in Phase 2+ can now call hooks directly — no API functions, no token management, no cache config needed at the component level.

## Next Phase Readiness

- All foundation hooks are available for Phase 2 (Dashboard) and Phase 3 (Transactions)
- useAnalytics hooks are ready with `enabled` flag for Phase 4 tab-based loading
- useInsights is ready for Phase 5 with appropriate cache settings
- No blockers — foundation complete

---
*Phase: 01-foundation*
*Completed: 2026-02-27*
