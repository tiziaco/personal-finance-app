---
phase: 01-foundation
plan: 05
type: execute
wave: 3
depends_on:
  - "03-PLAN"
files_modified:
  - web-app/src/hooks/use-transactions.ts
  - web-app/src/hooks/use-categories.ts
  - web-app/src/hooks/use-dashboard-summary.ts
  - web-app/src/hooks/use-analytics.ts
  - web-app/src/hooks/use-insights.ts
autonomous: true
requirements:
  - FOUND-03

must_haves:
  truths:
    - "useTransactions accepts filters and page number; uses placeholderData: keepPreviousData"
    - "useCategories returns CATEGORY_OPTIONS statically — makes NO API call"
    - "useDashboardSummary uses staleTime of 2 minutes"
    - "useAnalytics family hooks accept an enabled flag for lazy tab-based loading"
    - "useInsights uses staleTime of 10 minutes and gcTime of 30 minutes"
    - "All hooks call useAuth().getToken() INSIDE the queryFn (not in hook body)"
    - "No hook imports fetch() directly — all use API functions from lib/api/"
    - "All hook files have 'use client' directive"
  artifacts:
    - path: "web-app/src/hooks/use-transactions.ts"
      provides: "useTransactions(filters, page) — paginated + filtered transaction query"
      exports: ["useTransactions"]
    - path: "web-app/src/hooks/use-categories.ts"
      provides: "useCategories() — static CATEGORY_OPTIONS, no API call"
      exports: ["useCategories"]
    - path: "web-app/src/hooks/use-dashboard-summary.ts"
      provides: "useDashboardSummary(filters) — dashboard endpoint query"
      exports: ["useDashboardSummary"]
    - path: "web-app/src/hooks/use-analytics.ts"
      provides: "useSpendingAnalytics, useCategoriesAnalytics, useMerchantsAnalytics, useRecurringAnalytics, useBehaviorAnalytics, useAnomaliesAnalytics"
      exports:
        - useSpendingAnalytics
        - useCategoriesAnalytics
        - useMerchantsAnalytics
        - useRecurringAnalytics
        - useBehaviorAnalytics
        - useAnomaliesAnalytics
    - path: "web-app/src/hooks/use-insights.ts"
      provides: "useInsights() — insights query with long cache time"
      exports: ["useInsights"]
  key_links:
    - from: "web-app/src/hooks/use-transactions.ts"
      to: "web-app/src/lib/api/transactions.ts"
      via: "fetchTransactions import"
      pattern: "import.*fetchTransactions.*from.*@/lib/api/transactions"
    - from: "web-app/src/hooks/use-analytics.ts"
      to: "web-app/src/lib/api/analytics.ts"
      via: "fetch* function imports"
      pattern: "import.*from.*@/lib/api/analytics"
    - from: "web-app/src/hooks/use-insights.ts"
      to: "web-app/src/lib/api/insights.ts"
      via: "fetchInsights import"
      pattern: "import.*fetchInsights.*from.*@/lib/api/insights"
    - from: "web-app/src/hooks/use-transactions.ts"
      to: "@tanstack/react-query"
      via: "useQuery, keepPreviousData"
      pattern: "keepPreviousData"
---

<objective>
Create all React Query hooks that application pages will consume. These hooks are the final layer of the foundation — they wire Clerk auth token retrieval to the API functions from Plan 03, producing typed loading/error/data states.

Purpose: Pages and components never call API functions directly. They call these hooks, receive typed data, and render. The hooks handle token retrieval, caching, stale-while-revalidate, and error propagation.

Output: Five hook files in web-app/src/hooks/.
</objective>

<execution_context>
@/Users/tizianoiacovelli/.claude/get-shit-done/workflows/execute-plan.md
@/Users/tizianoiacovelli/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Prior plan outputs:
@web-app/src/lib/api/transactions.ts
@web-app/src/lib/api/analytics.ts
@web-app/src/lib/api/insights.ts
@web-app/src/types/transaction.ts
@web-app/src/types/analytics.ts
@web-app/src/types/insights.ts

Existing QueryProvider config (DO NOT CHANGE this file — read for reference only):
@web-app/src/providers/query-provider.tsx

**React Query v5 API constraints (breaking changes from v4):**
- Use `isPending` (not `isLoading`) for "no data yet" state. `isLoading` exists but has different semantics.
- Use `placeholderData: keepPreviousData` (not `keepPreviousData: true` which was v4 syntax). Import `keepPreviousData` from `@tanstack/react-query`.
- `staleTime` is already set globally to `60_000` (1 min) in QueryProvider. Per-hook values OVERRIDE the global. Set higher values for expensive endpoints.
- Do NOT set `staleTime: 0` — this causes double-fetch on navigation.

**Token retrieval rule:**
- Call `const { getToken } = useAuth()` in the hook body (outside queryFn)
- Call `const token = await getToken()` INSIDE the `queryFn` callback
- Never pass token as a prop or store it in component state

**useCategories special case:**
- There is NO `/categories` API endpoint on the backend
- Categories are a static TypeScript enum (CATEGORY_OPTIONS from types/transaction.ts)
- useCategories returns `{ data: CATEGORY_OPTIONS, isLoading: false, isError: false }` directly
- No useQuery, no getToken call needed
</context>

<interfaces>
<!-- API functions from Plan 03 that these hooks call. Executor should use these directly. -->

From web-app/src/lib/api/transactions.ts:
```typescript
export async function fetchTransactions(token: string | null, filters?: TransactionFilters): Promise<TransactionListResponse>
export async function updateTransaction(token: string | null, id: number, data: Partial<Pick<TransactionResponse, 'category'>>): Promise<TransactionResponse>
export async function batchUpdateTransactions(token: string | null, body: BatchUpdateRequest): Promise<BatchUpdateResponse>
export async function batchDeleteTransactions(token: string | null, body: BatchDeleteRequest): Promise<BatchDeleteResponse>
```

From web-app/src/lib/api/analytics.ts:
```typescript
export async function fetchDashboard(token: string | null, filters?: AnalyticsFilters): Promise<DashboardResponse>
export async function fetchSpendingAnalytics(token: string | null, filters?: AnalyticsFilters): Promise<AnalyticsResponse>
export async function fetchCategoriesAnalytics(token: string | null, filters?: AnalyticsFilters & { top_n?: number }): Promise<AnalyticsResponse>
export async function fetchMerchantsAnalytics(token: string | null, filters?: AnalyticsFilters & { top_n?: number }): Promise<AnalyticsResponse>
export async function fetchRecurringAnalytics(token: string | null, filters?: AnalyticsFilters): Promise<AnalyticsResponse>
export async function fetchBehaviorAnalytics(token: string | null, filters?: AnalyticsFilters): Promise<AnalyticsResponse>
export async function fetchAnomaliesAnalytics(token: string | null, filters?: AnalyticsFilters & { std_threshold?: number; rolling_window?: number }): Promise<AnalyticsResponse>
```

From web-app/src/lib/api/insights.ts:
```typescript
export async function fetchInsights(token: string | null): Promise<InsightsResponse>
```

From web-app/src/types/transaction.ts:
```typescript
export const CATEGORY_OPTIONS: CategoryEnum[]  // static array of 20 category strings
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Create transaction, categories, and dashboard hooks</name>
  <files>
    web-app/src/hooks/use-transactions.ts,
    web-app/src/hooks/use-categories.ts,
    web-app/src/hooks/use-dashboard-summary.ts
  </files>
  <action>
**File 1: web-app/src/hooks/use-transactions.ts**
```typescript
'use client'

import { useAuth } from '@clerk/nextjs'
import { useQuery, keepPreviousData } from '@tanstack/react-query'
import { fetchTransactions } from '@/lib/api/transactions'
import type { TransactionFilters, TransactionListResponse } from '@/types/transaction'

export function useTransactions(filters: TransactionFilters = {}, page: number = 0) {
  const { getToken } = useAuth()
  const limit = 25
  const offset = page * limit

  return useQuery<TransactionListResponse>({
    queryKey: ['transactions', filters, page],
    queryFn: async () => {
      const token = await getToken()
      return fetchTransactions(token, { ...filters, offset, limit })
    },
    placeholderData: keepPreviousData,   // keeps old page visible while fetching next — v5 syntax
    staleTime: 30 * 1000,               // 30 seconds — transactions change on upload
  })
}
```

**File 2: web-app/src/hooks/use-categories.ts**
```typescript
// Note: There is NO /categories API endpoint.
// Categories are a static TypeScript enum — this hook returns them without any API call.

import { CATEGORY_OPTIONS } from '@/types/transaction'
import type { CategoryEnum } from '@/types/transaction'

export function useCategories(): {
  data: CategoryEnum[]
  isLoading: false
  isError: false
} {
  return { data: CATEGORY_OPTIONS, isLoading: false, isError: false }
}
```

**File 3: web-app/src/hooks/use-dashboard-summary.ts**
```typescript
'use client'

import { useAuth } from '@clerk/nextjs'
import { useQuery } from '@tanstack/react-query'
import { fetchDashboard } from '@/lib/api/analytics'
import type { DashboardResponse, AnalyticsFilters } from '@/types/analytics'

export function useDashboardSummary(filters: AnalyticsFilters = {}) {
  const { getToken } = useAuth()

  return useQuery<DashboardResponse>({
    queryKey: ['dashboard', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchDashboard(token, filters)
    },
    staleTime: 2 * 60 * 1000,   // 2 minutes — dashboard data is relatively stable
  })
}
```
  </action>
  <verify>
    <automated>cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck 2>&1 | head -20</automated>
  </verify>
  <done>
    - use-transactions.ts uses keepPreviousData (v5 import) not the deprecated v4 option
    - use-categories.ts makes NO API call — returns CATEGORY_OPTIONS directly
    - use-dashboard-summary.ts uses staleTime: 2 * 60 * 1000
    - All hooks with useAuth have 'use client' directive
    - Zero TypeScript errors
  </done>
</task>

<task type="auto">
  <name>Task 2: Create analytics and insights hooks</name>
  <files>
    web-app/src/hooks/use-analytics.ts,
    web-app/src/hooks/use-insights.ts
  </files>
  <action>
**File 1: web-app/src/hooks/use-analytics.ts**

Each analytics hook accepts an `enabled` flag (default `true`) — this allows Phase 4 tab-based lazy loading: set `enabled: false` until the tab becomes active.

```typescript
'use client'

import { useAuth } from '@clerk/nextjs'
import { useQuery } from '@tanstack/react-query'
import {
  fetchSpendingAnalytics,
  fetchCategoriesAnalytics,
  fetchMerchantsAnalytics,
  fetchRecurringAnalytics,
  fetchBehaviorAnalytics,
  fetchAnomaliesAnalytics,
} from '@/lib/api/analytics'
import type { AnalyticsResponse, AnalyticsFilters } from '@/types/analytics'

const ANALYTICS_STALE_TIME = 5 * 60 * 1000  // 5 minutes — analytics are expensive to compute

export function useSpendingAnalytics(filters: AnalyticsFilters = {}, enabled = true) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'spending', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchSpendingAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}

export function useCategoriesAnalytics(
  filters: AnalyticsFilters & { top_n?: number } = {},
  enabled = true
) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'categories', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchCategoriesAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}

export function useMerchantsAnalytics(
  filters: AnalyticsFilters & { top_n?: number } = {},
  enabled = true
) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'merchants', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchMerchantsAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}

export function useRecurringAnalytics(filters: AnalyticsFilters = {}, enabled = true) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'recurring', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchRecurringAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}

export function useBehaviorAnalytics(filters: AnalyticsFilters = {}, enabled = true) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'behavior', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchBehaviorAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}

export function useAnomaliesAnalytics(
  filters: AnalyticsFilters & { std_threshold?: number; rolling_window?: number } = {},
  enabled = true
) {
  const { getToken } = useAuth()
  return useQuery<AnalyticsResponse>({
    queryKey: ['analytics', 'anomalies', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchAnomaliesAnalytics(token, filters)
    },
    enabled,
    staleTime: ANALYTICS_STALE_TIME,
  })
}
```

---

**File 2: web-app/src/hooks/use-insights.ts**

```typescript
'use client'

import { useAuth } from '@clerk/nextjs'
import { useQuery } from '@tanstack/react-query'
import { fetchInsights } from '@/lib/api/insights'
import type { InsightsResponse } from '@/types/insights'

export function useInsights() {
  const { getToken } = useAuth()

  return useQuery<InsightsResponse>({
    queryKey: ['insights'],
    queryFn: async () => {
      const token = await getToken()
      return fetchInsights(token)
    },
    staleTime: 10 * 60 * 1000,    // 10 min — insights are expensive (30s generation time)
    gcTime: 30 * 60 * 1000,       // 30 min — keep in cache while navigating away
  })
}
```
  </action>
  <verify>
    <automated>cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck 2>&1 | head -30</automated>
  </verify>
  <done>
    - use-analytics.ts exports 6 hooks: useSpendingAnalytics, useCategoriesAnalytics, useMerchantsAnalytics, useRecurringAnalytics, useBehaviorAnalytics, useAnomaliesAnalytics
    - Each analytics hook accepts enabled flag defaulting to true
    - use-insights.ts uses staleTime: 10 * 60 * 1000 and gcTime: 30 * 60 * 1000
    - All hooks call getToken() inside queryFn
    - Zero TypeScript errors
  </done>
</task>

</tasks>

<verification>
After both tasks complete:
1. `cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck` — zero errors
2. All 5 hook files exist in web-app/src/hooks/
3. Grep check: `keepPreviousData` appears in use-transactions.ts (v5 import style)
4. Grep check: use-categories.ts does NOT contain `useQuery` or `getToken` (static return only)
5. Grep check: all hook files except use-categories.ts have `'use client'` directive
6. Grep check: no `fetch(` call in any hook file (all delegate to API functions)
</verification>

<success_criteria>
- 5 hook files exist and compile without TypeScript errors
- useCategories makes zero API calls
- useTransactions uses placeholderData: keepPreviousData (v5 syntax)
- All analytics hooks have enabled flag for lazy loading
- getToken() called inside queryFn — never in hook body or component
- staleTime values: transactions=30s, dashboard=2m, analytics=5m, insights=10m
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-foundation-05-SUMMARY.md` with:
- List of all 5 hook files and their exports
- Confirmation that useCategories has no API call
- Confirmation of keepPreviousData usage in useTransactions
- TypeScript compilation status
- Full list of all Phase 1 deliverables now complete (types + API + hooks + charts + skeletons + error boundary)
</output>
