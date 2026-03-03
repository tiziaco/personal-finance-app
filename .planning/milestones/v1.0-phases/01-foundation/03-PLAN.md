---
phase: 01-foundation
plan: 03
type: execute
wave: 2
depends_on:
  - "01-PLAN"
files_modified:
  - web-app/src/lib/api/client.ts
  - web-app/src/lib/api/transactions.ts
  - web-app/src/lib/api/analytics.ts
  - web-app/src/lib/api/insights.ts
autonomous: true
requirements:
  - FOUND-02

must_haves:
  truths:
    - "A single apiRequest<T>() utility handles all auth header injection and error throwing"
    - "fetchTransactions converts TransactionFilters to URLSearchParams correctly"
    - "All 7 analytics endpoint functions exist and map to the correct URL paths"
    - "fetchInsights exists for GET /api/v1/insights"
    - "No component or hook calls fetch() directly — all go through apiRequest()"
    - "No Clerk token is passed as a prop — token is obtained inside each API function via the caller"
  artifacts:
    - path: "web-app/src/lib/api/client.ts"
      provides: "apiRequest<T>() shared authenticated fetch utility"
      exports: ["apiRequest"]
    - path: "web-app/src/lib/api/transactions.ts"
      provides: "fetchTransactions, updateTransaction, batchUpdateTransactions, batchDeleteTransactions"
      exports:
        - fetchTransactions
        - updateTransaction
        - batchUpdateTransactions
        - batchDeleteTransactions
    - path: "web-app/src/lib/api/analytics.ts"
      provides: "fetchDashboard, fetchSpendingAnalytics, fetchCategoriesAnalytics, fetchMerchantsAnalytics, fetchRecurringAnalytics, fetchBehaviorAnalytics, fetchAnomaliesAnalytics"
      exports:
        - fetchDashboard
        - fetchSpendingAnalytics
        - fetchCategoriesAnalytics
        - fetchMerchantsAnalytics
        - fetchRecurringAnalytics
        - fetchBehaviorAnalytics
        - fetchAnomaliesAnalytics
    - path: "web-app/src/lib/api/insights.ts"
      provides: "fetchInsights"
      exports: ["fetchInsights"]
  key_links:
    - from: "web-app/src/lib/api/transactions.ts"
      to: "web-app/src/lib/api/client.ts"
      via: "apiRequest import"
      pattern: "import.*apiRequest.*from.*./client"
    - from: "web-app/src/lib/api/analytics.ts"
      to: "web-app/src/lib/api/client.ts"
      via: "apiRequest import"
      pattern: "import.*apiRequest.*from.*./client"
    - from: "web-app/src/lib/api/insights.ts"
      to: "web-app/src/lib/api/client.ts"
      via: "apiRequest import"
      pattern: "import.*apiRequest.*from.*./client"
---

<objective>
Create the typed API client layer: a shared fetch utility and four domain-specific API function modules. These functions are the only code that talks to the backend — hooks and components never call fetch() directly.

Purpose: Centralize auth header injection and error handling in one place. Every API call goes through apiRequest() which constructs the URL from NEXT_PUBLIC_API_URL, injects the Clerk Bearer token, and throws on non-2xx responses. Domain modules (transactions.ts, analytics.ts, insights.ts) provide typed functions that hooks in Plan 05 will call.

Output: web-app/src/lib/api/client.ts + three domain API modules.
</objective>

<execution_context>
@/Users/tizianoiacovelli/.claude/get-shit-done/workflows/execute-plan.md
@/Users/tizianoiacovelli/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md

Prior plan output: Plan 01 created the type files. Read their exports before implementing.
@web-app/src/types/transaction.ts
@web-app/src/types/analytics.ts
@web-app/src/types/insights.ts

Existing pattern to follow exactly (do not change this file):
@web-app/src/lib/api/health.ts

**Analytics endpoints map (from server/app/api/v1/analytics.py):**
```
GET /api/v1/analytics/dashboard               → DashboardResponse
GET /api/v1/analytics/spending                → AnalyticsResponse  (accepts date_from, date_to)
GET /api/v1/analytics/categories              → AnalyticsResponse  (accepts date_from, date_to, top_n: int = 10)
GET /api/v1/analytics/merchants               → AnalyticsResponse  (accepts date_from, date_to, top_n: int = 10)
GET /api/v1/analytics/recurring               → AnalyticsResponse  (accepts date_from, date_to)
GET /api/v1/analytics/behavior                → AnalyticsResponse  (accepts date_from, date_to)
GET /api/v1/analytics/anomalies               → AnalyticsResponse  (accepts date_from, date_to, std_threshold: float = 2.0, rolling_window: int = 3)
GET /api/v1/insights                          → InsightsResponse
GET /api/v1/transactions                      → TransactionListResponse (accepts all TransactionFilters fields)
PATCH /api/v1/transactions/{id}               → TransactionResponse (body: Partial<TransactionResponse>)
PATCH /api/v1/transactions/batch              → BatchUpdateResponse (body: BatchUpdateRequest)
DELETE /api/v1/transactions/batch             → BatchDeleteResponse (body: BatchDeleteRequest)
```

**Key constraints:**
- `apiRequest<T>()` takes `path: string`, `token: string | null`, optional `options?: RequestInit`
- Base URL from `process.env.NEXT_PUBLIC_API_URL` — never hardcode localhost
- Always set `cache: 'no-store'` to prevent Next.js static caching of financial data
- Token is passed AS A PARAMETER to API functions — never retrieved inside client.ts (the hook's queryFn retrieves the token and passes it in)
- Throw `new Error()` on non-ok responses — React Query catches this and sets `isError: true`
</context>

<interfaces>
<!-- Types from Plan 01 that these API functions consume. Executor should use these directly. -->

From web-app/src/types/transaction.ts:
```typescript
export type CategoryEnum = 'Income' | 'Transportation' | 'Salary' | ... // 20 values

export interface TransactionResponse {
  id: number; user_id: string; date: string; merchant: string;
  amount: string; // string, not number
  description: string | null; original_category: string | null;
  category: CategoryEnum; confidence_score: number; is_recurring: boolean;
  created_at: string; updated_at: string;
}

export interface TransactionListResponse {
  items: TransactionResponse[]; total: number; offset: number; limit: number;
}

export interface TransactionFilters {
  date_from?: string; date_to?: string; category?: CategoryEnum; merchant?: string;
  amount_min?: string; amount_max?: string; is_recurring?: boolean;
  sort_by?: 'date' | 'amount' | 'merchant'; sort_order?: 'asc' | 'desc';
  offset?: number; limit?: number;
}

export interface BatchUpdateRequest { items: BatchUpdateItem[]; }
export interface BatchUpdateResponse { updated: number; }
export interface BatchDeleteRequest { ids: number[]; }
export interface BatchDeleteResponse { deleted: number; }
```

From web-app/src/types/analytics.ts:
```typescript
export interface AnalyticsResponse { data: Record<string, unknown>; generated_at: string; }
export interface DashboardResponse {
  spending: Record<string, unknown>; categories: Record<string, unknown>;
  recurring: Record<string, unknown>; trends: Record<string, unknown>;
  generated_at: string;
}
export interface AnalyticsFilters { date_from?: string; date_to?: string; }
```

From web-app/src/types/insights.ts:
```typescript
export interface InsightsResponse { insights: Insight[]; generated_at: string; }
```
</interfaces>

<tasks>

<task type="auto">
  <name>Task 1: Create shared API client utility</name>
  <files>web-app/src/lib/api/client.ts</files>
  <action>
Create `web-app/src/lib/api/client.ts`:

```typescript
/**
 * Shared authenticated fetch utility.
 * All API calls go through this function — never call fetch() directly in hooks or components.
 */
export async function apiRequest<T>(
  path: string,
  token: string | null,
  options?: RequestInit
): Promise<T> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}${path}`
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
    cache: 'no-store',
  })
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${path}`)
  }
  return response.json() as Promise<T>
}
```

No other exports. No imports needed (uses built-in fetch).
  </action>
  <verify>
    <automated>cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck 2>&1 | head -20</automated>
  </verify>
  <done>
    - web-app/src/lib/api/client.ts exists and exports apiRequest
    - Function signature: (path: string, token: string | null, options?: RequestInit) => Promise&lt;T&gt;
    - Uses NEXT_PUBLIC_API_URL env var
    - Sets cache: 'no-store'
    - Throws on non-ok responses
    - Zero TypeScript errors
  </done>
</task>

<task type="auto">
  <name>Task 2: Create domain API function modules</name>
  <files>
    web-app/src/lib/api/transactions.ts,
    web-app/src/lib/api/analytics.ts,
    web-app/src/lib/api/insights.ts
  </files>
  <action>
**File 1: web-app/src/lib/api/transactions.ts**

```typescript
import type {
  TransactionListResponse,
  TransactionResponse,
  TransactionFilters,
  BatchUpdateRequest,
  BatchUpdateResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
} from '@/types/transaction'
import { apiRequest } from './client'

export async function fetchTransactions(
  token: string | null,
  filters: TransactionFilters = {}
): Promise<TransactionListResponse> {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      params.set(key, String(value))
    }
  })
  const query = params.toString()
  return apiRequest<TransactionListResponse>(
    `/api/v1/transactions${query ? `?${query}` : ''}`,
    token
  )
}

export async function updateTransaction(
  token: string | null,
  id: number,
  data: Partial<Pick<TransactionResponse, 'category'>>
): Promise<TransactionResponse> {
  return apiRequest<TransactionResponse>(`/api/v1/transactions/${id}`, token, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function batchUpdateTransactions(
  token: string | null,
  body: BatchUpdateRequest
): Promise<BatchUpdateResponse> {
  return apiRequest<BatchUpdateResponse>('/api/v1/transactions/batch', token, {
    method: 'PATCH',
    body: JSON.stringify(body),
  })
}

export async function batchDeleteTransactions(
  token: string | null,
  body: BatchDeleteRequest
): Promise<BatchDeleteResponse> {
  return apiRequest<BatchDeleteResponse>('/api/v1/transactions/batch', token, {
    method: 'DELETE',
    body: JSON.stringify(body),
  })
}
```

---

**File 2: web-app/src/lib/api/analytics.ts**

Create one function per analytics endpoint. Each accepts `token: string | null` and an optional filters/params object:

```typescript
import type { AnalyticsResponse, DashboardResponse, AnalyticsFilters } from '@/types/analytics'
import { apiRequest } from './client'

function buildAnalyticsQuery(filters: AnalyticsFilters & Record<string, unknown> = {}): string {
  const params = new URLSearchParams()
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      params.set(key, String(value))
    }
  })
  const q = params.toString()
  return q ? `?${q}` : ''
}

export async function fetchDashboard(
  token: string | null,
  filters: AnalyticsFilters = {}
): Promise<DashboardResponse> {
  return apiRequest<DashboardResponse>(`/api/v1/analytics/dashboard${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchSpendingAnalytics(
  token: string | null,
  filters: AnalyticsFilters = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/spending${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchCategoriesAnalytics(
  token: string | null,
  filters: AnalyticsFilters & { top_n?: number } = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/categories${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchMerchantsAnalytics(
  token: string | null,
  filters: AnalyticsFilters & { top_n?: number } = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/merchants${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchRecurringAnalytics(
  token: string | null,
  filters: AnalyticsFilters = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/recurring${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchBehaviorAnalytics(
  token: string | null,
  filters: AnalyticsFilters = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/behavior${buildAnalyticsQuery(filters)}`, token)
}

export async function fetchAnomaliesAnalytics(
  token: string | null,
  filters: AnalyticsFilters & { std_threshold?: number; rolling_window?: number } = {}
): Promise<AnalyticsResponse> {
  return apiRequest<AnalyticsResponse>(`/api/v1/analytics/anomalies${buildAnalyticsQuery(filters)}`, token)
}
```

---

**File 3: web-app/src/lib/api/insights.ts**

```typescript
import type { InsightsResponse } from '@/types/insights'
import { apiRequest } from './client'

export async function fetchInsights(token: string | null): Promise<InsightsResponse> {
  return apiRequest<InsightsResponse>('/api/v1/insights', token)
}
```
  </action>
  <verify>
    <automated>cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck 2>&1 | head -20</automated>
  </verify>
  <done>
    - web-app/src/lib/api/transactions.ts exports: fetchTransactions, updateTransaction, batchUpdateTransactions, batchDeleteTransactions
    - web-app/src/lib/api/analytics.ts exports: fetchDashboard, fetchSpendingAnalytics, fetchCategoriesAnalytics, fetchMerchantsAnalytics, fetchRecurringAnalytics, fetchBehaviorAnalytics, fetchAnomaliesAnalytics
    - web-app/src/lib/api/insights.ts exports: fetchInsights
    - All 3 files import from ./client (not from fetch directly)
    - Zero TypeScript errors
  </done>
</task>

</tasks>

<verification>
After both tasks complete:
1. `cd /Users/tizianoiacovelli/projects/personal-finance-app/web-app && npx tsc --noEmit --skipLibCheck` — zero errors
2. All 4 files exist: client.ts, transactions.ts, analytics.ts, insights.ts
3. Grep check: no `fetch(` call in transactions.ts, analytics.ts, or insights.ts (all go through apiRequest)
4. Grep check: no `process.env.NEXT_PUBLIC_API_URL` in domain files (only in client.ts)
</verification>

<success_criteria>
- apiRequest<T>() is the only place fetch() is called
- All 7 analytics functions map to the correct /api/v1/analytics/* paths
- Token parameter is `string | null` (not string) — handles unauthenticated edge cases
- TypeScript compilation passes with zero errors
</success_criteria>

<output>
After completion, create `.planning/phases/01-foundation/01-foundation-03-SUMMARY.md` with:
- List of all 4 files created and their exports
- Confirmation that all analytics endpoints are covered
- TypeScript compilation status
- Any deviations (e.g., different function signatures than planned)
</output>
