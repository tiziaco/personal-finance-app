# Phase 4: Analytics - Research

**Researched:** 2026-03-01
**Domain:** React tabbed analytics page with lazy-loaded charts (Next.js 16, React 19, Base UI Tabs, Recharts via shadcn Chart)
**Confidence:** HIGH

---

## Summary

Phase 4 builds the Analytics page at the `/stats` route (already registered in `HUB_NAV` and the app layout as a stub). The page presents four analytics dimensions — spending by category, income vs expenses, month-over-month trends, and seasonality — using a tabbed layout. The core challenge is lazy loading: each tab must trigger its data fetch only when first activated, and must never re-fetch if the user switches back.

The project already has all necessary infrastructure: `@base-ui/react` v1.2.0 (installed) provides a `Tabs` component with natural lazy-loading behavior (`keepMounted` defaults to `false`, so panels unmount when hidden). Six analytics hooks exist in `src/hooks/use-analytics.ts` — all accept an `enabled` flag specifically designed for this pattern (STATE.md decision: "Analytics hooks accept enabled=true flag — supports Phase 4 tab-based lazy loading without refactoring at call site"). Shared `BarChart`, `LineChart`, and `PieChart` wrappers exist in `src/components/shared/charts/`. The backend exposes `/api/v1/analytics/{spending,categories,behavior}` which map directly to the four tab requirements.

**Primary recommendation:** Build a controlled `Tabs.Root` (base-ui) tracking `activeTab` and a `Set<string>` of visited tabs in page state. Pass `enabled={visitedTabs.has('tab-name')}` to each analytics hook. This delivers ANLT-06 (lazy load) with React Query's built-in caching ensuring no re-fetch on return visits.

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| ANLT-01 | User sees an Analytics page with tabbed navigation (shadcn Tabs component) for each analytics dimension | Base UI Tabs (`@base-ui/react/tabs`) is installed at v1.2.0; `Tabs.Root/List/Tab/Panel` API confirmed; project uses base-ui for all UI primitives (Button, etc.) |
| ANLT-02 | User can view spending by category tab with pie/bar chart and quick date filters (1M / 3M / 6M) | `useCategoriesAnalytics(filters, enabled)` hook exists; `fetchCategoriesAnalytics` hits `/api/v1/analytics/categories`; `AnalyticsFilters` accepts `date_from/date_to`; `PieChart` component ready |
| ANLT-03 | User can view income vs expenses tab showing a bar chart by month with a cash flow summary | `useSpendingAnalytics(filters, enabled)` hook exists; `/api/v1/analytics/spending` returns `overview.income_vs_expenses[]` and `overview.stats[]`; `BarChart` component ready |
| ANLT-04 | User can view month-over-month trends tab with a line chart comparing spending across months | Same `useSpendingAnalytics` hook; response includes `recent_trend.last_3_months` and `overview.stats[]` with `expense_mom_growth`; `LineChart` component ready |
| ANLT-05 | User can view seasonality tab showing spending patterns by month of year and day of week | `useBehaviorAnalytics(filters, enabled)` hook exists; `/api/v1/analytics/behavior` returns `day_of_week.by_weekday[]` and `seasonality.monthly_patterns[]`; `BarChart` usable for both |
| ANLT-06 | Analytics tabs lazy-load their data only when the tab becomes active (not all on mount) | Base UI `Tabs.Panel` unmounts by default (`keepMounted=false`); `enabled` flag on all hooks; controlled `activeTab` + `visitedTabs` Set pattern gates fetches precisely |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `@base-ui/react` (Tabs) | 1.2.0 | Tabbed navigation UI | Already installed; project uses it for all primitives (Button, etc.); accessible, headless, Tailwind-compatible |
| `@tanstack/react-query` | ^5.90 | Analytics data fetching with caching | Already in use; `enabled` flag drives lazy-load; `staleTime=5min` set for analytics hooks |
| `recharts` (via shadcn Chart) | ^2.15 | All charts (pie, bar, line) | Shared chart wrappers already exist in `src/components/shared/charts/` |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `lucide-react` | ^0.575 | Tab icons, empty state icons | Available; used throughout project |
| `sonner` | ^2.0 | Error toasts | Already used in ErrorBoundary |
| shadcn `Card` / `CardHeader` / `CardContent` | project | Chart container structure | Used in all dashboard chart components — same pattern here |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Base UI Tabs | shadcn Tabs (radix-based) | Radix not installed; Base UI is the project standard; adding shadcn Tabs would add radix as a dep |
| `enabled` flag pattern | URL params for tab state | URL params are correct for shareable tabs; for now, stateful is sufficient per requirements |
| `useBehaviorAnalytics` for ANLT-05 | Two separate hooks | Single endpoint returns both day-of-week and monthly seasonality; one fetch is enough |

**Installation:** No new packages needed. All dependencies are already installed.

---

## Architecture Patterns

### Recommended Project Structure

```
src/app/(app)/stats/
└── page.tsx                    # AnalyticsPage — tab state owner + composition

src/components/analytics/
├── spending-by-category-tab.tsx   # ANLT-02: PieChart + date filter buttons
├── income-vs-expenses-tab.tsx     # ANLT-03: BarChart + cash flow summary
├── trends-tab.tsx                 # ANLT-04: LineChart month-over-month
└── seasonality-tab.tsx            # ANLT-05: two BarCharts (monthly + day-of-week)
```

This mirrors the pattern established in Phase 2: `src/components/dashboard/` widgets, composed by `src/app/(app)/home/page.tsx`.

### Pattern 1: Controlled Tab + Visited-Set Lazy Loading

**What:** Page owns `activeTab` (string) and `visitedTabs` (Set<string>). Each tab panel's analytics hook receives `enabled={visitedTabs.has(tabValue)}`. When the user clicks a tab, `activeTab` updates and the tab value is added to `visitedTabs`. React Query caches the result so revisiting the tab does NOT re-fetch.

**When to use:** Whenever ANLT-06 must be satisfied — data only fetched on first activation, never on revisit.

**Example:**
```typescript
// Source: project pattern + React Query docs
'use client'

import { useState } from 'react'
import { Tabs } from '@base-ui/react/tabs'

const TABS = ['category', 'income-expenses', 'trends', 'seasonality'] as const
type TabValue = typeof TABS[number]

export default function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState<TabValue>('category')
  const [visitedTabs, setVisitedTabs] = useState<Set<TabValue>>(new Set(['category']))

  function handleTabChange(value: TabValue) {
    setActiveTab(value)
    setVisitedTabs(prev => new Set([...prev, value]))
  }

  return (
    <Tabs.Root value={activeTab} onValueChange={(v) => handleTabChange(v as TabValue)}>
      <Tabs.List>
        <Tabs.Tab value="category">By Category</Tabs.Tab>
        <Tabs.Tab value="income-expenses">Income vs Expenses</Tabs.Tab>
        <Tabs.Tab value="trends">Trends</Tabs.Tab>
        <Tabs.Tab value="seasonality">Seasonality</Tabs.Tab>
      </Tabs.List>

      <Tabs.Panel value="category">
        <SpendingByCategoryTab enabled={visitedTabs.has('category')} />
      </Tabs.Panel>
      <Tabs.Panel value="income-expenses">
        <IncomeVsExpensesTab enabled={visitedTabs.has('income-expenses')} />
      </Tabs.Panel>
      {/* ... */}
    </Tabs.Root>
  )
}
```

### Pattern 2: Date Filter State — Local to Tab Component

**What:** The 1M / 3M / 6M date filter (ANLT-02) is local state inside `SpendingByCategoryTab`. It computes `date_from` from today's date and passes it to `useCategoriesAnalytics({ date_from, date_to })`. Changing the filter updates the query key and triggers a new fetch (React Query caches per key).

**Example:**
```typescript
// Source: confirmed from AnalyticsFilters type + React Query key behavior
'use client'

import { useCategoriesAnalytics } from '@/hooks/use-analytics'

type DateRange = '1M' | '3M' | '6M'

function getDateFrom(range: DateRange): string {
  const d = new Date()
  if (range === '1M') d.setMonth(d.getMonth() - 1)
  else if (range === '3M') d.setMonth(d.getMonth() - 3)
  else d.setMonth(d.getMonth() - 6)
  return d.toISOString().split('T')[0]  // YYYY-MM-DD
}

interface SpendingByCategoryTabProps { enabled: boolean }

export function SpendingByCategoryTab({ enabled }: SpendingByCategoryTabProps) {
  const [range, setRange] = useState<DateRange>('3M')
  const dateFrom = getDateFrom(range)
  const { data, isLoading } = useCategoriesAnalytics(
    { date_from: dateFrom },
    enabled
  )
  // render PieChart with data?.data.top_categories
}
```

### Pattern 3: Backend Data Narrowing Inside Tab Component

**What:** `AnalyticsResponse.data` is typed as `Record<string, unknown>` (STATE.md: "narrowing deferred to Phase 2/4"). Each tab component narrows `data.data` to the shape it expects via an inline interface + type assertion. Same approach used in Dashboard phase for `DashboardResponse` sub-fields.

**Example:**
```typescript
// Narrow inside tab component after confirming backend shape
interface CategoryAnalyticsData {
  top_categories: Array<{ category: string; total_amount: number; percentage: number }>
  frequency_vs_impact: Record<string, unknown>[]
  category_trends: { top_growing: Record<string, unknown>[]; top_declining: Record<string, unknown>[] }
}

const analyticsData = data?.data as CategoryAnalyticsData | undefined
const topCategories = analyticsData?.top_categories ?? []
```

### Pattern 4: Base UI Tabs Styling with Tailwind

**What:** Base UI Tabs exposes `data-[active]` attribute on `Tabs.Tab` for active styling. Use `data-[active]:` Tailwind variant.

**Example:**
```typescript
// Source: Context7 / base-ui.com official docs
<Tabs.Tab
  value="category"
  className="px-4 py-2 text-sm font-medium text-muted-foreground
             data-[active]:text-foreground data-[active]:border-b-2
             data-[active]:border-primary transition-colors"
>
  By Category
</Tabs.Tab>
```

### Anti-Patterns to Avoid

- **Fetching all tabs on mount:** Passing `enabled={true}` unconditionally to all four hooks. This loads 3 endpoints the user never opens, wasting bandwidth and violating ANLT-06.
- **URL-syncing tab state:** Not required by the spec. Adds complexity without stated benefit. Keep tab state local to the page component.
- **Re-computing `visitedTabs` via `activeTab` alone:** Using only `activeTab` to derive `enabled` causes re-fetch every tab switch. The `Set<string>` accumulates visits and is the gating mechanism.
- **Importing `shadcn` Tabs:** The requirement says "shadcn Tabs component" as a design-system reference, but `@radix-ui/react-tabs` is NOT installed. Use `@base-ui/react/tabs` which is the project's actual component library.
- **Using `keepMounted={true}` on `Tabs.Panel`:** This would keep all panels in the DOM but still allow re-fetching on every tab switch unless `enabled` is managed separately. The default `keepMounted=false` is the right behavior here.

---

## API Endpoint → Tab Mapping

This is the critical mapping to get right before planning:

| Tab (ANLT req) | Hook | Endpoint | Key fields in `data.data` |
|---|---|---|---|
| Spending by Category (ANLT-02) | `useCategoriesAnalytics` | `GET /api/v1/analytics/categories` | `top_categories[]{category, total_amount, percentage}` |
| Income vs Expenses (ANLT-03) | `useSpendingAnalytics` | `GET /api/v1/analytics/spending` | `overview.income_vs_expenses[]{month, total_income, total_expense, net}` + `overview.stats[]{month, total_expense, total_income, net}` |
| Month-over-Month Trends (ANLT-04) | `useSpendingAnalytics` | `GET /api/v1/analytics/spending` (same call, different fields) | `overview.stats[]{month, total_expense, expense_mom_growth}` + `recent_trend.last_3_months[]` |
| Seasonality (ANLT-05) | `useBehaviorAnalytics` | `GET /api/v1/analytics/behavior` | `day_of_week.by_weekday[]{day_name, total_spending}` + `seasonality.monthly_patterns[]{month, ...}` |

**Key insight for ANLT-03 and ANLT-04:** Both use `useSpendingAnalytics`. If the user opens both tabs, only ONE network call will fire (React Query deduplicates identical queryKeys). However, the tab components should still each manage their own `enabled` flag so neither fires until its tab is first visited.

**Important:** `useSpendingAnalytics` is called TWICE (once for income-expenses tab, once for trends tab). Both calls use the same queryKey `['analytics', 'spending', {}]` (no filters on these tabs), so React Query serves the second from cache — no double fetch.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tabs with lazy-loaded content | Custom CSS visibility toggle | `@base-ui/react/tabs` with `enabled` flags | Accessibility (keyboard nav, ARIA), correct unmounting behavior, animated indicator |
| Chart components | Custom SVG charts | Existing `BarChart`, `LineChart`, `PieChart` in `src/components/shared/charts/` | Already use Recharts + shadcn ChartContainer with correct OKLCH colors |
| Date filter math | String concatenation | `new Date()` with `toISOString().split('T')[0]` | Standard JS; no library needed |
| Loading skeletons | Custom pulse divs | `ChartSkeleton` in `src/components/shared/skeletons/chart-skeleton.tsx` | Consistent with dashboard and transactions pages |
| Error boundaries | Try-catch in render | `ErrorBoundary` in `src/components/shared/error-boundary.tsx` | Already in use on every page |

**Key insight:** Phase 1 and 2 deliberately built all the chart and skeleton infrastructure for this phase. Zero new UI primitives are needed.

---

## Common Pitfalls

### Pitfall 1: `enabled` Flag Not Propagating Correctly

**What goes wrong:** Tab component receives `enabled` prop but passes it to the hook only when not undefined, causing fetch to fire on first render before the tab is active.

**Why it happens:** `enabled={visitedTabs.has('tab')}` evaluates to `false` correctly, but if the tab component calls the hook unconditionally (ignoring the prop), it fires immediately.

**How to avoid:** Always pass `enabled` as the second argument to the analytics hook: `useSpendingAnalytics({}, enabled)`. The hook signature is `(filters, enabled = true)`.

**Warning signs:** Network tab shows 4 analytics requests on initial page load instead of 1.

---

### Pitfall 2: `data.data` Type Cast — Wrong Shape Assumed

**What goes wrong:** `AnalyticsResponse.data` is `Record<string, unknown>`. Casting to the wrong shape (e.g., assuming `data.data.top_categories` when calling `/spending` endpoint) causes silent undefined access.

**Why it happens:** Three different endpoints all return `AnalyticsResponse` with `data: Record<string, unknown>`. The shape varies by endpoint.

**How to avoid:** Define a concrete TypeScript interface per tab matching the exact backend shape (confirmed from `server/app/tools/financial.py`). See API Endpoint → Tab Mapping section above.

**Warning signs:** Chart renders with empty data even though network request returned 200.

---

### Pitfall 3: React Query Key Collision Between Tabs

**What goes wrong:** Trends tab and Income vs Expenses tab both call `useSpendingAnalytics({})`. If either adds date filters later, the shared key means one tab's filter change invalidates the other.

**Why it happens:** `queryKey: ['analytics', 'spending', filters]` — both tabs share the same key with `filters = {}`.

**How to avoid:** In Phase 4, neither of these tabs has date filters (only Category tab has 1M/3M/6M). Treat this as acceptable sharing. Document clearly in component file so Phase 5/6 devs don't add a filter to one without considering the other.

**Warning signs:** Changing date range on one tab causes the other tab's chart to update unexpectedly.

---

### Pitfall 4: Base UI Tabs `onValueChange` Type

**What goes wrong:** `onValueChange` receives `Tabs.Tab.Value` which is typed as `string | number`. TypeScript will complain when casting to a string union type.

**Why it happens:** Base UI's generic tab value type allows both string and number values.

**How to avoid:**
```typescript
onValueChange={(v) => handleTabChange(v as TabValue)}
```
This is a safe cast since all tab values are strings in our usage. Document this decision as a project pattern.

**Warning signs:** TypeScript error: "Type 'string | number' is not assignable to type 'TabValue'".

---

### Pitfall 5: ANLT-02 Date Filter — `date_to` Not Needed

**What goes wrong:** Setting `date_to` to today's date explicitly seems correct but is unnecessary. The backend already filters to available data when no `date_to` is provided.

**Why it happens:** Defensive programming instinct.

**How to avoid:** Only pass `date_from` in the filter. Leave `date_to` undefined. This matches how all existing hooks are used.

---

## Code Examples

Verified patterns from official sources and project codebase:

### Base UI Tabs — Full Pattern (Controlled + Lazy Load)

```typescript
// Source: base-ui.com official docs + project patterns
'use client'

import { useState } from 'react'
import { Tabs } from '@base-ui/react/tabs'
import { cn } from '@/lib/utils'

export default function AnalyticsPage() {
  const [activeTab, setActiveTab] = useState('category')
  const [visitedTabs, setVisitedTabs] = useState<Set<string>>(new Set(['category']))

  const handleTabChange = (value: string | number) => {
    const tab = String(value)
    setActiveTab(tab)
    setVisitedTabs(prev => new Set([...prev, tab]))
  }

  return (
    <div className="container max-w-6xl mx-auto py-8 space-y-6">
      <h1 className="text-2xl font-bold">Analytics</h1>

      <Tabs.Root value={activeTab} onValueChange={handleTabChange}>
        <Tabs.List className="relative flex border-b border-border gap-0">
          {[
            { value: 'category', label: 'By Category' },
            { value: 'income-expenses', label: 'Income vs Expenses' },
            { value: 'trends', label: 'Trends' },
            { value: 'seasonality', label: 'Seasonality' },
          ].map(tab => (
            <Tabs.Tab
              key={tab.value}
              value={tab.value}
              className={cn(
                'px-4 py-2 text-sm font-medium text-muted-foreground',
                'data-[active]:text-foreground data-[active]:border-b-2 data-[active]:border-primary',
                'focus-visible:outline-none transition-colors'
              )}
            >
              {tab.label}
            </Tabs.Tab>
          ))}
        </Tabs.List>

        <Tabs.Panel value="category" className="pt-6">
          <SpendingByCategoryTab enabled={visitedTabs.has('category')} />
        </Tabs.Panel>
        <Tabs.Panel value="income-expenses" className="pt-6">
          <IncomeVsExpensesTab enabled={visitedTabs.has('income-expenses')} />
        </Tabs.Panel>
        <Tabs.Panel value="trends" className="pt-6">
          <TrendsTab enabled={visitedTabs.has('trends')} />
        </Tabs.Panel>
        <Tabs.Panel value="seasonality" className="pt-6">
          <SeasonalityTab enabled={visitedTabs.has('seasonality')} />
        </Tabs.Panel>
      </Tabs.Root>
    </div>
  )
}
```

### Narrowing `AnalyticsResponse.data` for Categories

```typescript
// Source: server/app/tools/financial.py get_category_insights() return shape
interface CategoryAnalyticsData {
  top_categories: Array<{
    category: string
    total_amount: number
    transaction_count: number
    percentage: number
  }>
  frequency_vs_impact: Record<string, unknown>[]
  confidence_weighted: Record<string, unknown>[]
  category_trends: {
    top_growing: Record<string, unknown>[]
    top_declining: Record<string, unknown>[]
  }
}

// In SpendingByCategoryTab:
const narrowed = data?.data as CategoryAnalyticsData | undefined
const topCategories = narrowed?.top_categories ?? []
```

### Narrowing `AnalyticsResponse.data` for Spending

```typescript
// Source: server/app/tools/financial.py get_spending_summary() return shape
interface SpendingAnalyticsData {
  overview: {
    stats: Array<{
      month: string          // "2026-02" format
      total_expense: number
      total_income: number
      net: number
    }>
    income_vs_expenses: Array<{
      month: string
      total_income: number
      total_expense: number
      net: number
    }>
  }
  recent_trend: {
    last_3_months: Array<{
      month: string
      total_expense: number
      total_income: number
      net: number
    }>
    burn_rate: Record<string, unknown>[]
  }
  date_range: { start: string | null; end: string | null; total_days: number }
}
```

### Narrowing `AnalyticsResponse.data` for Behavior

```typescript
// Source: server/app/tools/financial.py get_behavioral_patterns() return shape
interface BehaviorAnalyticsData {
  day_of_week: {
    by_weekday: Array<{
      weekday: number
      day_name: string        // "Monday", "Tuesday", etc.
      total_spending: number
      avg_transaction: number
      transaction_count: number
      percentage: number
    }>
    weekday_vs_weekend: Array<{
      day_type: string        // "weekday" | "weekend"
      total_spending: number
      avg_per_day: number
    }>
    weekend_bias_percentage: number | null
  }
  seasonality: {
    monthly_patterns: Array<{
      month: number           // 1-12
      // additional fields from analyze_seasonality_simple()
    }>
    quarterly_patterns: Record<string, unknown>[]
  }
  volatility: {
    stable_categories: Record<string, unknown>[]
    volatile_categories: Record<string, unknown>[]
  }
  insights: {
    weekend_spender: boolean
    most_stable_category: string | null
    most_volatile_category: string | null
  }
}
```

### Date Range Filter Helper

```typescript
// Source: project pattern — date_from is YYYY-MM-DD per AnalyticsFilters type
type DateRange = '1M' | '3M' | '6M'

function getDateFrom(range: DateRange): string {
  const d = new Date()
  const months = range === '1M' ? 1 : range === '3M' ? 3 : 6
  d.setMonth(d.getMonth() - months)
  return d.toISOString().split('T')[0]  // "2026-02-01"
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Radix UI Tabs (shadcn default) | Base UI Tabs (`@base-ui/react`) | Phase 1 setup | No Radix deps; must use `@base-ui/react/tabs`, not shadcn `tabs` component |
| Eager data loading | `enabled` flag on React Query | Phase 1 decision (STATE.md) | Tab lazy-load already designed into hooks; no hook refactor needed in Phase 4 |
| `hsl(var(--chart-N))` color syntax | `var(--chart-N)` directly | Phase 1 decision (STATE.md) | Must use `var(--chart-N)` in chart configs, NOT `hsl(var(--chart-N))` |
| `AnalyticsResponse.data: any` | `Record<string, unknown>` narrowed in Phase 4 | Deferred from Phase 1 (STATE.md) | Each tab must narrow the type; Phase 4 is where this deferred work happens |

**Deprecated/outdated:**
- shadcn `tabs` component: Not applicable — radix is not installed. Use `@base-ui/react/tabs` directly.

---

## Open Questions

1. **`seasonality.monthly_patterns` exact column names**
   - What we know: `analyze_seasonality_simple()` returns `monthly_seasonality` DataFrame; field names not fully inspected
   - What's unclear: Exact column names (`month`, `month_name`, `avg_spending`, etc.) in the serialized dict
   - Recommendation: Before implementing SeasonalityTab, read `server/app/analytics/temporal.py::analyze_seasonality_simple` to confirm column names. The `month` column is likely an integer (1-12); may need a month name lookup for display.

2. **`income_vs_expenses` vs `stats` for ANLT-03**
   - What we know: `spending` endpoint returns both `overview.income_vs_expenses[]` and `overview.stats[]`; both contain monthly income/expense data
   - What's unclear: Which is the authoritative source for the monthly bar chart
   - Recommendation: Use `overview.stats[]` which has `month`, `total_expense`, `total_income`, `net` — confirmed from `DashboardSpendingStat` type already defined in `types/analytics.ts`.

3. **`stats` route vs `analytics` route naming**
   - What we know: `HUB_NAV` uses `/stats` as the URL; the stub page is at `app/(app)/stats/page.tsx`
   - What's unclear: Whether Phase 4 should rename this to `/analytics` for clarity
   - Recommendation: Keep `/stats` — it's already registered in the sidebar nav and would require updating `HUB_NAV`. The page title can be "Analytics" without matching the URL slug.

---

## Sources

### Primary (HIGH confidence)

- `/websites/base-ui_react` (Context7) — Tabs component API: `Root`, `List`, `Tab`, `Panel`, `Indicator`; `keepMounted` prop; `data-[active]` attribute; `onValueChange` signature
- `web-app/src/hooks/use-analytics.ts` — All six analytics hooks with `enabled` parameter (direct codebase read)
- `server/app/tools/financial.py` — Exact return shapes for `get_spending_summary()`, `get_category_insights()`, `get_behavioral_patterns()` (direct codebase read)
- `web-app/src/types/analytics.ts` — `AnalyticsResponse`, `AnalyticsFilters`, `DashboardSpendingStat` types (direct codebase read)
- `.planning/STATE.md` — Locked decisions: `enabled` flag pattern, `var(--chart-N)` color tokens, `Record<string, unknown>` narrowing deferred to Phase 4, EUR locale

### Secondary (MEDIUM confidence)

- `server/app/analytics/temporal.py` — `analyze_day_of_week_patterns()` return schema partially inspected (exact column names for seasonality data partially confirmed)
- `server/app/analytics/descriptive.py` — `calculate_spending_overview()` return shape confirmed at API level

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed installed and in use in codebase
- Architecture: HIGH — all hooks, types, and chart wrappers confirmed; pattern is established by Phase 2/3
- Pitfalls: HIGH — derived from existing codebase patterns and STATE.md decisions
- Backend data shapes: HIGH for spending/categories, MEDIUM for seasonality (monthly_patterns column names partially unverified)

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (stable stack; only risk is seasonal data column names needing verification before SeasonalityTab implementation)
