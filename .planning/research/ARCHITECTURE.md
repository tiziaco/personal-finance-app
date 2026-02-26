# Architecture Patterns

**Domain:** Personal finance dashboard frontend (Next.js 16 App Router)
**Researched:** 2026-02-26
**Confidence:** HIGH — based on existing codebase inspection + verified patterns

---

## Recommended Architecture

The frontend follows a **Client-first architecture with server layouts** pattern. The existing codebase has no server-side data fetching — all data comes from a FastAPI backend via the Clerk-authenticated API client. Every page that fetches data must be a Client Component (or contain Client Component children). Server Components handle layout, metadata, and static structure only.

```
web-app/src/
├── app/
│   └── (app)/
│       ├── layout.tsx              ← Server Component: sidebar shell (existing)
│       ├── home/
│       │   └── page.tsx            ← Server Component: no data, renders <DashboardPage />
│       ├── transactions/
│       │   └── page.tsx            ← Server Component: no data, renders <TransactionsPage />
│       ├── analytics/
│       │   └── page.tsx            ← Server Component: no data, renders <AnalyticsPage />
│       ├── insights/
│       │   └── page.tsx            ← Server Component: no data, renders <InsightsPage />
│       └── budgets/
│           └── page.tsx            ← Server Component: placeholder only
├── components/
│   ├── ui/                         ← shadcn primitives (existing, never modify)
│   ├── layout/                     ← Sidebar, nav (existing, never modify)
│   ├── shared/                     ← Cross-page reusable components
│   │   ├── charts/                 ← Chart wrapper components (always "use client")
│   │   │   ├── pie-chart.tsx
│   │   │   ├── line-chart.tsx
│   │   │   ├── bar-chart.tsx
│   │   │   └── area-chart.tsx
│   │   ├── transaction-table/      ← Reused on Dashboard + Transactions pages
│   │   │   ├── transaction-table.tsx
│   │   │   ├── transaction-filters.tsx
│   │   │   └── transaction-row.tsx
│   │   ├── skeleton/               ← Loading state components
│   │   │   ├── card-skeleton.tsx
│   │   │   ├── table-skeleton.tsx
│   │   │   └── chart-skeleton.tsx
│   │   └── empty-state.tsx
│   ├── dashboard/                  ← Dashboard-specific components
│   │   ├── dashboard-page.tsx      ← "use client" root for dashboard
│   │   ├── summary-cards.tsx
│   │   ├── recent-transactions.tsx
│   │   └── insights-callout.tsx
│   ├── transactions/               ← Transactions-specific components
│   │   ├── transactions-page.tsx   ← "use client" root for transactions
│   │   ├── category-edit-modal.tsx
│   │   ├── bulk-action-bar.tsx
│   │   └── csv-upload-button.tsx
│   ├── analytics/                  ← Analytics-specific components
│   │   ├── analytics-page.tsx      ← "use client" root for analytics
│   │   ├── analytics-tabs.tsx
│   │   ├── spending-by-category-tab.tsx
│   │   ├── income-expenses-tab.tsx
│   │   ├── trends-tab.tsx
│   │   └── seasonality-tab.tsx
│   └── insights/                   ← Insights-specific components
│       ├── insights-page.tsx       ← "use client" root for insights
│       ├── generate-button.tsx
│       ├── insight-card.tsx
│       └── insights-grid.tsx
├── hooks/
│   ├── use-mobile.ts               ← existing
│   ├── use-server-status.ts        ← existing
│   ├── use-transactions.ts         ← React Query wrapper for /transactions
│   ├── use-analytics.ts            ← React Query wrapper for /analytics/*
│   ├── use-insights.ts             ← React Query wrapper for /insights
│   └── use-dashboard.ts            ← React Query wrapper for /analytics/dashboard
├── lib/
│   └── api/
│       ├── health.ts               ← existing
│       ├── client.ts               ← NEW: shared authenticated fetch utility
│       ├── transactions.ts         ← API functions for /transactions
│       ├── analytics.ts            ← API functions for /analytics/*
│       └── insights.ts             ← API function for /insights
└── types/
    ├── transaction.ts              ← TypeScript types matching backend schemas
    ├── analytics.ts
    └── insights.ts
```

---

## Server Component vs Client Component Split

This is the most critical architectural decision. The rule is simple and absolute:

**Server Components:** `(app)/layout.tsx` (sidebar shell), all `page.tsx` files (they only render a client component child), static loading UI shells.

**Client Components:** Everything that touches React Query, Clerk auth tokens, `useState`, `useEffect`, charts, filters, or interactive UI.

### Why page.tsx stays a Server Component

Each `page.tsx` file is a thin shell that imports and renders the feature's "page client component." This keeps metadata, layout, and routing in the server, while delegating all data-fetching and interactivity to a client boundary.

```tsx
// app/(app)/home/page.tsx — Server Component (no "use client")
import { DashboardPage } from "@/components/dashboard/dashboard-page"

export default function HomePage() {
  return <DashboardPage />
}
```

```tsx
// components/dashboard/dashboard-page.tsx — Client Component
"use client"

import { useDashboard } from "@/hooks/use-dashboard"
// ... full interactive page
```

### The "use client" boundary rule

Once a component has `"use client"`, ALL its imported components are also client-side — even if they don't have the directive. This means:

- Chart wrappers: always `"use client"` (react-charts is browser-only, ESM-only)
- Filter components: always `"use client"` (useState)
- Modal components: always `"use client"` (useState, dialog state)
- Page root components: `"use client"` because they use React Query hooks

**Never mark shadcn `ui/` primitives as server-only** — they already work as both. Import them freely in client components.

### react-charts Specific Constraint (HIGH confidence)

TanStack React Charts (`react-charts@beta`) depends on `d3-time-format`, which is ESM-only. Next.js webpack cannot bundle it server-side. **All chart components must be wrapped in dynamic imports with SSR disabled:**

```tsx
// components/shared/charts/line-chart.tsx
"use client"

import dynamic from "next/dynamic"

const ChartComponent = dynamic(
  () => import("./line-chart-impl").then((m) => m.LineChartImpl),
  {
    ssr: false,
    loading: () => <ChartSkeleton />,
  }
)

export function LineChart(props: LineChartProps) {
  return <ChartComponent {...props} />
}
```

The `loading` prop on `dynamic()` doubles as the skeleton state — no extra conditional needed.

---

## API Client Pattern

All API calls follow the existing pattern in `lib/api/health.ts`: plain async functions that accept a Clerk token and call `fetch()` against `NEXT_PUBLIC_API_URL`.

### Shared client utility

```typescript
// lib/api/client.ts
export async function apiRequest<T>(
  path: string,
  token: string | null,
  options?: RequestInit
): Promise<T> {
  const url = `${process.env.NEXT_PUBLIC_API_URL}${path}`
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options?.headers,
    },
  })
  if (!response.ok) {
    throw new Error(`API error ${response.status}: ${path}`)
  }
  return response.json()
}
```

### Token pattern with Clerk

All React Query hooks obtain the Clerk token via `useAuth()`:

```typescript
import { useAuth } from "@clerk/nextjs"
import { useQuery } from "@tanstack/react-query"

export function useDashboard(dateFrom?: string, dateTo?: string) {
  const { getToken } = useAuth()

  return useQuery({
    queryKey: ["dashboard", dateFrom, dateTo],
    queryFn: async () => {
      const token = await getToken()
      return fetchDashboard(token, { dateFrom, dateTo })
    },
    staleTime: 2 * 60 * 1000, // 2 minutes — dashboard data is relatively stable
  })
}
```

---

## React Query Integration Patterns

### Paginated Transactions Table

The transactions endpoint returns `{ items, total, offset, limit }`. Use `keepPreviousData` (React Query v5: `placeholderData: keepPreviousData`) to avoid table flash on page change.

```typescript
// hooks/use-transactions.ts
export function useTransactions(filters: TransactionFilters, page: number) {
  const { getToken } = useAuth()
  const limit = 25
  const offset = page * limit

  return useQuery({
    queryKey: ["transactions", filters, page],
    queryFn: async () => {
      const token = await getToken()
      return fetchTransactions(token, { ...filters, offset, limit })
    },
    placeholderData: keepPreviousData, // keeps old data visible while fetching next page
    staleTime: 30 * 1000,
  })
}
```

**Query key structure** for transactions includes all filter parameters so cache is properly keyed:
```
["transactions", { category, merchant, dateFrom, dateTo, sortBy, sortOrder }, page]
```

Changing any filter resets the page to 0. This is handled in the filter component via a `setPage(0)` call alongside the filter state setter.

### Analytics Queries (Multi-Tab)

Each analytics tab maps to a separate backend endpoint. Fetch lazily — only when the tab becomes active — using the `enabled` flag:

```typescript
// hooks/use-analytics.ts
export function useSpendingAnalytics(
  dateFrom?: string,
  dateTo?: string,
  enabled = true
) {
  const { getToken } = useAuth()
  return useQuery({
    queryKey: ["analytics", "spending", dateFrom, dateTo],
    queryFn: async () => {
      const token = await getToken()
      return fetchSpendingAnalytics(token, { dateFrom, dateTo })
    },
    enabled,           // only fetches when this tab is active
    staleTime: 5 * 60 * 1000,
  })
}
```

In the analytics page component, track active tab in state and pass `enabled={activeTab === "spending"}` to each hook. React Query caches the result so switching tabs back is instant.

### Insights Query (Cache-First)

The insights endpoint is GET-only with server-side caching. The frontend has no "generate" button that triggers a separate generation call — the backend auto-generates on first call and after CSV imports. The correct frontend pattern is:

- `GET /api/v1/insights` on page load
- If the response is empty or stale, the user can trigger a manual refetch using `refetch()` from React Query
- No polling loop — the backend generates synchronously on the first call (as per the API description: "On first call (no cache), generates synchronously")
- A "Regenerate" button calls `refetch()` with a manual invalidation, subject to a UI-enforced cooldown

```typescript
// hooks/use-insights.ts
export function useInsights() {
  const { getToken } = useAuth()

  return useQuery({
    queryKey: ["insights"],
    queryFn: async () => {
      const token = await getToken()
      return fetchInsights(token)
    },
    staleTime: 10 * 60 * 1000, // 10 minutes — insights are expensive to generate
    gcTime: 30 * 60 * 1000,
  })
}
```

The "Regenerate" button is a separate concern from the query. It uses `queryClient.invalidateQueries({ queryKey: ["insights"] })` which triggers a fresh fetch. The button tracks cooldown via local `useState` and `setTimeout`.

```typescript
// components/insights/generate-button.tsx
"use client"

const [cooldown, setCooldown] = useState(false)
const queryClient = useQueryClient()

function handleRegenerate() {
  setCooldown(true)
  queryClient.invalidateQueries({ queryKey: ["insights"] })
  setTimeout(() => setCooldown(false), 60_000) // 1 minute cooldown
}
```

### Mutation Pattern (Category Edit, Batch Delete)

Use `useMutation` for all write operations. Invalidate the transactions query after success so the table refreshes:

```typescript
export function useUpdateTransaction() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, data }: { id: number; data: TransactionUpdate }) => {
      const token = await getToken()
      return updateTransaction(token, id, data)
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["transactions"] })
      queryClient.invalidateQueries({ queryKey: ["dashboard"] }) // dashboard shows recent transactions
    },
  })
}
```

---

## Component Boundaries

| Component | Type | Communicates With |
|-----------|------|-------------------|
| `(app)/layout.tsx` | Server | Renders sidebar shell + `{children}` |
| `(app)/home/page.tsx` | Server | Renders `<DashboardPage />` |
| `components/dashboard/dashboard-page.tsx` | Client | `useDashboard`, `useTransactions`, `useInsights` hooks |
| `components/shared/transaction-table/` | Client | Receives data via props from parent page |
| `components/shared/charts/*` | Client (dynamic, no SSR) | Receives data via props |
| `components/analytics/analytics-tabs.tsx` | Client | Manages active tab state, renders tab content |
| `components/insights/generate-button.tsx` | Client | `useQueryClient` for invalidation |
| `lib/api/*.ts` | Isomorphic functions | Called by React Query hooks only |
| `hooks/use-*.ts` | Client-only (React Query) | Called from Client Components |

### Shared vs Page-Specific Components

**Shared (`components/shared/`):** Use when a component appears on 2+ pages or represents a pure data display pattern.
- `transaction-table/` — used on Dashboard (recent 5) and Transactions page (full list)
- `charts/` — all chart primitives, used across Dashboard and Analytics
- `skeleton/` — loading states used everywhere
- `empty-state.tsx` — used on Transactions and Insights pages

**Page-specific (`components/{page}/`):** Use when a component is tightly coupled to one page's data shape, layout, or interaction model.
- `dashboard/summary-cards.tsx` — only makes sense on Dashboard
- `transactions/category-edit-modal.tsx` — only on Transactions page
- `analytics/spending-by-category-tab.tsx` — only in Analytics tabs
- `insights/insight-card.tsx` — only on Insights page

The `transaction-table` component should accept a `mode` prop or use composition to handle the difference between "recent 5" (dashboard) vs "full paginated" (transactions page):

```tsx
// Shared component with flexible rendering
<TransactionTable
  transactions={data.items}
  mode="compact"         // "compact" | "full"
  showPagination={false}
/>
```

---

## Data Flow

```
Clerk Auth (ClerkProvider in root layout.tsx)
    ↓ useAuth() → getToken()
React Query hooks (hooks/use-*.ts)
    ↓ apiRequest() with Bearer token
lib/api/*.ts → fetch() → FastAPI backend
    ↓ JSON response
React Query cache (QueryProvider in root layout.tsx)
    ↓ data, isLoading, isError
Page client components (components/{page}/page.tsx)
    ↓ props
Child display components (charts, tables, cards)
    ↓ rendered HTML
User's browser
```

State flows down through props. No shared state between pages except what React Query's cache provides (which is correct — a mutation on Transactions invalidates Dashboard's recent-transactions query).

---

## Suggested Build Order

Build in this order. Each phase's output is a dependency for the next.

### Phase 1: Infrastructure (build first, blocks everything)

1. `lib/api/client.ts` — shared authenticated fetch utility
2. `lib/api/transactions.ts` — all transaction API functions
3. `lib/api/analytics.ts` — all analytics API functions
4. `lib/api/insights.ts` — insights API function
5. `types/transaction.ts`, `types/analytics.ts`, `types/insights.ts` — TypeScript types matching Pydantic schemas
6. `hooks/use-transactions.ts`, `hooks/use-analytics.ts`, `hooks/use-insights.ts`, `hooks/use-dashboard.ts`

Rationale: All page components depend on these. Build and manually test (console.log) these before building any UI.

### Phase 2: Shared display components (no data dependency, pure props)

7. `components/shared/skeleton/` — card, table, chart skeletons
8. `components/shared/empty-state.tsx`
9. `components/shared/charts/` — pie, line, bar chart wrappers (with dynamic import + SSR disabled)
10. `components/shared/transaction-table/` — table, filters, row

Rationale: These are pure display components that accept props. Build them with hardcoded mock data first, then wire to hooks.

### Phase 3: Dashboard page (priority per PROJECT.md)

11. `components/dashboard/summary-cards.tsx`
12. `components/dashboard/recent-transactions.tsx` (uses shared `transaction-table`)
13. `components/dashboard/insights-callout.tsx`
14. `components/dashboard/dashboard-page.tsx` — assembles all dashboard components with `useDashboard` hook
15. Update `app/(app)/home/page.tsx` to render `<DashboardPage />`

Rationale: Dashboard is the first page users see. Uses all shared components. Validates the full data → hook → component flow.

### Phase 4: Transactions page

16. `components/transactions/category-edit-modal.tsx`
17. `components/transactions/bulk-action-bar.tsx`
18. `components/transactions/transactions-page.tsx` — full paginated table with filters
19. Update `app/(app)/transactions/page.tsx`

Rationale: Heaviest interaction page. Pagination, filters, mutations. Build after dashboard so the pattern is proven.

### Phase 5: Analytics page

20. `components/analytics/spending-by-category-tab.tsx`
21. `components/analytics/income-expenses-tab.tsx`
22. `components/analytics/trends-tab.tsx`
23. `components/analytics/seasonality-tab.tsx`
24. `components/analytics/analytics-tabs.tsx` — tab switcher with lazy loading
25. `components/analytics/analytics-page.tsx`
26. Create `app/(app)/analytics/page.tsx`

Rationale: Depends on chart wrappers (Phase 2) and analytics hooks (Phase 1). Four tabs can be built independently.

### Phase 6: Insights page

27. `components/insights/insight-card.tsx`
28. `components/insights/insights-grid.tsx`
29. `components/insights/generate-button.tsx`
30. `components/insights/insights-page.tsx`
31. Create `app/(app)/insights/page.tsx`

### Phase 7: Budgets placeholder + responsive polish

32. Create `app/(app)/budgets/page.tsx` — "Coming Soon" static component
33. Mobile responsive: sidebar collapse, hamburger menu, 48px tap targets
34. Design tokens: apply teal/warm gray/cream palette via tailwind.config.js

---

## Async Insights Pattern: Detailed Breakdown

The insights endpoint is NOT truly async in the fire-and-poll sense. From the API code:

```python
# insights.py: "On first call (no cache), generates synchronously."
row = await insights_service.get_insights(db, user.id)
return InsightsResponse(...)
```

This means the first GET request will block until generation is complete (could be 5-30 seconds for an LLM call). Subsequent calls return cached data instantly.

### Recommended UI approach

```
User opens Insights page
    → useInsights() fires GET /insights
    → If isLoading: show full-page skeleton + "Generating your insights..." message
    → If data: render insight cards grid
    → If isError: show error state with retry button
    → "Regenerate" button: invalidate cache → triggers new GET (blocks again)
```

**Do NOT poll.** The backend generates synchronously on the first request. Polling would create multiple concurrent generation requests (rate-limited at 10/minute). The correct pattern is a single query with a long timeout tolerance.

Configure React Query's `gcTime` to be long (30 minutes) so navigating away and back doesn't re-trigger generation:

```typescript
useQuery({
  queryKey: ["insights"],
  staleTime: 10 * 60 * 1000,  // 10 min: don't refetch if less than 10 min old
  gcTime: 30 * 60 * 1000,     // 30 min: keep in cache even if no subscribers
})
```

### First-load UX

Show a meaningful loading state during the synchronous generation. A skeleton grid with "Analyzing your spending patterns..." messaging is better than a spinner, as it sets expectations.

---

## State Management Approach

**No global state manager needed.** React Query handles all server state. Local component state (`useState`) handles UI state (active tab, selected rows, modal open/closed, filter values).

| State Type | Tool | Example |
|------------|------|---------|
| Server data (transactions, analytics, insights) | React Query | `useTransactions()`, `useDashboard()` |
| Filter form values | `useState` in filter component | `const [category, setCategory] = useState(null)` |
| Pagination page number | `useState` in page component | `const [page, setPage] = useState(0)` |
| Active analytics tab | `useState` in analytics page | `const [tab, setTab] = useState("spending")` |
| Selected transaction rows | `useState` in transactions page | `const [selected, setSelected] = useState<Set<number>>` |
| Modal open state | `useState` in parent component | `const [editModal, setEditModal] = useState(null)` |
| Toast notifications | sonner (already configured) | `toast.success("Category updated")` |

No need for Zustand, Jotai, or Context API for this scope. React Query's cache is the single source of truth for data.

---

## Patterns to Follow

### Pattern 1: Skeleton-first loading

Never show empty content during loading. Every data-fetching component renders a skeleton when `isLoading`:

```tsx
if (isLoading) return <CardSkeleton count={4} />
if (isError) return <EmptyState message="Could not load data" />
if (!data?.items?.length) return <EmptyState message="No transactions yet" />
return <TransactionTable transactions={data.items} />
```

### Pattern 2: Error boundary at page level

Wrap each page client component in React's `ErrorBoundary` to catch unexpected rendering errors without crashing the whole app. shadcn doesn't provide one — use a simple custom implementation or the `react-error-boundary` package.

### Pattern 3: Optimistic UI for category edits

When a user edits a transaction category, update the UI immediately before the API call completes:

```typescript
useMutation({
  mutationFn: updateTransaction,
  onMutate: async ({ id, data }) => {
    await queryClient.cancelQueries({ queryKey: ["transactions"] })
    const previous = queryClient.getQueryData(["transactions"])
    queryClient.setQueryData(["transactions", ...], (old) => /* update locally */)
    return { previous }
  },
  onError: (err, variables, context) => {
    queryClient.setQueryData(["transactions"], context.previous) // rollback
    toast.error("Failed to update category")
  },
  onSuccess: () => {
    toast.success("Category updated")
  },
})
```

### Pattern 4: Filter state in URL (optional enhancement)

For deep-linking and browser back/forward support on the transactions page, store filters in URL search params using `useSearchParams` from Next.js. This is optional for MVP but makes the app feel more native.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Fetching in Server Components

**What:** Using `fetch()` directly in `page.tsx` Server Components to pre-fetch data.
**Why bad:** Clerk tokens are not available server-side in this setup (the proxy.ts is a client-side middleware), and it creates a split between server-fetched and client-fetched data that React Query cannot cache or deduplicate.
**Instead:** Keep all data fetching in Client Components via React Query hooks.

### Anti-Pattern 2: Importing react-charts without dynamic()

**What:** `import { Chart } from "react-charts"` at the top of any component.
**Why bad:** The d3-time-format dependency is ESM-only and breaks the Next.js webpack build.
**Instead:** Always use `dynamic(() => import("react-charts"), { ssr: false })`.

### Anti-Pattern 3: One giant page component

**What:** Putting all JSX for a page (summary cards + charts + table) in a single `dashboard-page.tsx`.
**Why bad:** Hard to maintain, no granular loading states, one render error crashes the whole page.
**Instead:** Each visual section is its own component with its own loading/error state.

### Anti-Pattern 4: Prop-drilling tokens

**What:** Passing `token` from a page component down through 4 layers of children.
**Why bad:** Couples display components to auth concerns. Hard to test.
**Instead:** Call `useAuth()` only in hooks (`use-transactions.ts`, etc.). Display components receive only data, never tokens.

### Anti-Pattern 5: Fetching all analytics tabs on mount

**What:** Firing all 5 analytics API calls (`/spending`, `/categories`, `/merchants`, etc.) when the Analytics page loads.
**Why bad:** 5 concurrent requests for data the user may never view. Rate limit is 30/minute.
**Instead:** Use `enabled: activeTab === "tabName"` to lazy-load each tab on first visit.

### Anti-Pattern 6: Modifying shadcn `ui/` components

**What:** Editing files in `components/ui/` directly.
**Why bad:** shadcn regenerates these files on `npx shadcn add`. Edits will be lost.
**Instead:** Wrap `ui/` components in new components in `components/shared/` or page directories.

---

## Scalability Considerations

This is a small personal app (friends + family), so scalability is not a primary concern. These notes apply if the user base grows.

| Concern | Current Scale | If Growing |
|---------|--------------|------------|
| React Query cache size | Fine — ~10 users, <1000 transactions | Add `gcTime` limits |
| Analytics data volume | Fine — all computed server-side | Already paginated |
| Bundle size | Monitor — react-charts is large | Dynamic import already handles this |
| Real-time updates | Not needed | Consider React Query polling (`refetchInterval`) |

---

## Sources

- Next.js App Router Server/Client Component docs: [https://nextjs.org/docs/app/getting-started/server-and-client-components](https://nextjs.org/docs/app/getting-started/server-and-client-components) — HIGH confidence
- TanStack Query Advanced SSR: [https://tanstack.com/query/latest/docs/framework/react/guides/advanced-ssr](https://tanstack.com/query/latest/docs/framework/react/guides/advanced-ssr) — HIGH confidence
- react-charts Next.js ESM issue: [https://github.com/TanStack/react-charts/issues/324](https://github.com/TanStack/react-charts/issues/324) — HIGH confidence (confirmed in issue thread)
- react-charts installation: [https://react-charts.tanstack.com/docs/installation](https://react-charts.tanstack.com/docs/installation) — HIGH confidence
- React Query infinite query: [https://tanstack.com/query/v5/docs/framework/react/examples/load-more-infinite-scroll](https://tanstack.com/query/v5/docs/framework/react/examples/load-more-infinite-scroll) — HIGH confidence
- Existing codebase inspection: `web-app/src/`, `server/app/api/v1/` — HIGH confidence (direct source read)

---

*Architecture analysis: 2026-02-26*
