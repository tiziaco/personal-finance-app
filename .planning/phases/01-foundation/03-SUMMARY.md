---
phase: 01-foundation
plan: 03
subsystem: api
tags: [typescript, fetch, react-query, clerk, next.js]

# Dependency graph
requires:
  - phase: 01-foundation
    plan: 01
    provides: TypeScript types for TransactionResponse, AnalyticsResponse, InsightsResponse
provides:
  - apiRequest<T>() shared authenticated fetch utility (client.ts)
  - fetchTransactions, updateTransaction, batchUpdateTransactions, batchDeleteTransactions (transactions.ts)
  - fetchDashboard, fetchSpendingAnalytics, fetchCategoriesAnalytics, fetchMerchantsAnalytics, fetchRecurringAnalytics, fetchBehaviorAnalytics, fetchAnomaliesAnalytics (analytics.ts)
  - fetchInsights (insights.ts)
affects:
  - 01-foundation-05 (hooks call these API functions)
  - Phase 2 Dashboard (fetchDashboard, fetchSpendingAnalytics)
  - Phase 3 Transactions (fetchTransactions, updateTransaction, batchUpdateTransactions, batchDeleteTransactions)
  - Phase 4 Analytics (all analytics functions)
  - Phase 5 Insights (fetchInsights)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - All HTTP calls go through apiRequest<T>() — never fetch() directly in hooks or components
    - Token is passed as parameter (string | null) — never retrieved inside client.ts
    - NEXT_PUBLIC_API_URL only referenced in client.ts
    - cache: 'no-store' on all requests to prevent Next.js static caching of financial data

key-files:
  created:
    - web-app/src/lib/api/client.ts
    - web-app/src/lib/api/transactions.ts
    - web-app/src/lib/api/analytics.ts
    - web-app/src/lib/api/insights.ts
  modified: []

key-decisions:
  - "buildAnalyticsQuery uses object parameter type to satisfy TypeScript strict mode — avoids index signature incompatibility with AnalyticsFilters while still iterating entries correctly"

patterns-established:
  - "API layer pattern: one shared client with Bearer token injection + domain modules that call apiRequest, never fetch()"
  - "Query string building: URLSearchParams with undefined/null filtering applied consistently in both transactions.ts and analytics.ts"

requirements-completed:
  - FOUND-02

# Metrics
duration: 2min
completed: 2026-02-27
---

# Phase 1 Plan 03: API Client Layer Summary

**Typed API client layer with centralized auth-header injection via apiRequest<T>() and 12 domain functions covering all transaction, analytics, and insights endpoints**

## Performance

- **Duration:** 2 min
- **Started:** 2026-02-27T06:40:05Z
- **Completed:** 2026-02-27T06:42:00Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Single apiRequest<T>() utility centralizes fetch(), Bearer token injection, cache: 'no-store', and error throwing
- 4 transaction functions cover CRUD/batch operations against /api/v1/transactions
- 7 analytics functions map to all /api/v1/analytics/* endpoints with correct filter parameter shapes
- 1 insights function covers GET /api/v1/insights
- Zero TypeScript errors in our files (pre-existing tailwind.config.ts error is unrelated)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create shared API client utility** - `b21dd80` (feat)
2. **Task 2: Create domain API function modules** - `f0e3d98` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `web-app/src/lib/api/client.ts` - Shared authenticated fetch utility, sole location of fetch() and NEXT_PUBLIC_API_URL
- `web-app/src/lib/api/transactions.ts` - fetchTransactions, updateTransaction, batchUpdateTransactions, batchDeleteTransactions
- `web-app/src/lib/api/analytics.ts` - fetchDashboard + 6 analytics endpoint functions with query string builder
- `web-app/src/lib/api/insights.ts` - fetchInsights

## Decisions Made

- `buildAnalyticsQuery` uses `object` parameter type instead of `AnalyticsFilters & Record<string, unknown>` — TypeScript strict mode requires an explicit index signature on interfaces to be assignable to Record<string, unknown>; using `object` with an internal cast is cleaner than widening the AnalyticsFilters interface definition.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed TypeScript incompatibility in buildAnalyticsQuery parameter type**
- **Found during:** Task 2 (Create domain API function modules)
- **Issue:** Plan specified `AnalyticsFilters & Record<string, unknown>` as the parameter type for `buildAnalyticsQuery`, but TypeScript strict mode rejects assigning `AnalyticsFilters` (which lacks an index signature) to `Record<string, unknown>`
- **Fix:** Changed parameter type to `object` with an internal cast `as Record<string, unknown>` for Object.entries() — preserves identical runtime behavior, satisfies TypeScript
- **Files modified:** web-app/src/lib/api/analytics.ts
- **Verification:** `npx tsc --noEmit --skipLibCheck` passes with zero errors in our files
- **Committed in:** f0e3d98 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - TypeScript type error)
**Impact on plan:** Auto-fix necessary for TypeScript compilation. No scope creep. Runtime behavior identical to the plan's intent.

## Issues Encountered

- TypeScript strict mode rejected the planned `AnalyticsFilters & Record<string, unknown>` intersection type — resolved by using `object` parameter type with internal cast.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- API layer complete: Plan 05 (React Query hooks) can import these functions and pass Clerk tokens from `useAuth()`
- All 12 endpoint functions are typed end-to-end: request params → response types
- The token is `string | null` throughout — hooks handle the null case by disabling queries until authenticated

---
*Phase: 01-foundation*
*Completed: 2026-02-27*
