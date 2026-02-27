# Phase 2: Dashboard - Research

**Researched:** 2026-02-27
**Domain:** Next.js 16 / React 19 dashboard page composition with Recharts/shadcn Chart, Clerk user context, and typed DashboardResponse narrowing
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DASH-01 | User sees a welcome card with their name and total spending this month | `useUser()` from `@clerk/nextjs` provides `firstName`; `DashboardResponse.spending` contains monthly stats via `get_spending_summary` |
| DASH-02 | User sees 4 summary cards (Total Spent, Remaining Budget, Recurring Costs, Savings Goal) with color coding | `DashboardResponse.spending.overview.stats` + `DashboardResponse.recurring.insights.total_recurring_percentage`; color via Tailwind utility classes on `CardSkeleton` base |
| DASH-03 | User sees spending-by-category pie chart (top 5 with legend and percentages) | `DashboardResponse.categories.top_categories` array (pre-narrowed); re-uses `PieChart` wrapper with `showLegend=true` |
| DASH-04 | User sees 6-month trend line chart with hover tooltips | `DashboardResponse.trends.monthly_trend` (last 12 entries from backend, slice to 6 in UI); re-uses `LineChart` wrapper |
| DASH-05 | User sees last 5-10 transactions with "View All" link | `useTransactions({ limit: 10, sort_by: 'date', sort_order: 'desc' })` — hook already built in Phase 1 |
| DASH-06 | User sees AI insights callout (1-2 highlights) with Generate CTA and new-data badge | `useInsights()` — hook already built in Phase 1; badge logic tracks `generated_at` vs last transaction date |
| DASH-07 | "Upload CSV" primary CTA navigates to upload flow | `next/link` or `router.push('/upload')` — route must exist or be stubbed |
| DASH-08 | "View Insights" secondary CTA navigates to Insights page | `next/link` to `/insights` — route already exists as `stats` page; may need renaming |
</phase_requirements>

---

## Summary

Phase 2 builds the home dashboard page at `app/(app)/home/page.tsx`, which is currently a one-line stub. All foundational infrastructure is complete from Phase 1: typed hooks (`useDashboardSummary`, `useTransactions`, `useInsights`), chart wrappers (`PieChart`, `LineChart`), skeleton components (`CardSkeleton`, `ChartSkeleton`, `InsightCardSkeleton`, `TableSkeleton`), and the `ErrorBoundary` class component. The primary task is composition: assemble widgets using existing primitives, narrow the `Record<string, unknown>` dashboard types to concrete interfaces, and wire up CTAs to the correct routes.

The most important technical challenge is type narrowing. `DashboardResponse.spending`, `.categories`, `.recurring`, and `.trends` are all `Record<string, unknown>` in the current TypeScript types — a deliberate deferral from Phase 1 documented in STATE.md. Phase 2 must define narrow TypeScript interfaces for these fields, cast at the hook boundary, and guarantee that chart and card components receive correctly typed data. The backend's `financial.py` tools are the authoritative source of truth for these shapes.

The second challenge is currency formatting. STATE.md mandates EUR (de-DE locale) as the default throughout. All monetary amounts from the API are `string`-typed decimal values (e.g., `"1234.56"`) — they must be parsed with `parseFloat` and formatted with `new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' })` at the display layer, never stored as floats.

**Primary recommendation:** Compose the dashboard as a single page with five sections (WelcomeCard, SummaryCards, ChartsRow, RecentTransactions, InsightsCallout), each isolated behind its own `ErrorBoundary`, using existing Phase 1 primitives. Define narrow sub-interfaces for dashboard response fields in `types/analytics.ts` and cast them in `useDashboardSummary`.

---

## Standard Stack

### Core (all already installed — no new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| next | 16.1.6 | App Router, `use client` pages | Framework |
| react | 19.2.4 | Component model | Framework |
| @clerk/nextjs | ^6.38.1 | `useUser()` for name, `useAuth()` for token | Auth layer |
| @tanstack/react-query | ^5.90.21 | `useDashboardSummary`, `useTransactions`, `useInsights` | Data fetching — already wired |
| recharts | ^2.15.4 | Chart rendering via shadcn Chart wrappers | Chosen in Phase 1 |
| lucide-react | ^0.575.0 | Icons (TrendingUp, CreditCard, etc.) | Already installed |
| sonner | ^2.0.7 | Toast notifications | Already installed |
| next/link | — | CTA navigation | Built-in Next.js |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shadcn/ui Card | (shadcn ^3.8.5) | Summary cards, widget containers | All cards |
| shadcn/ui Badge | (shadcn ^3.8.5) | "New data" badge on insights callout | DASH-06 |
| shadcn/ui Skeleton | (shadcn ^3.8.5) | Loading states via CardSkeleton, ChartSkeleton | All loading states |
| clsx + tailwind-merge | installed | Conditional color classes (green/red) | Color-coded cards |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| shadcn Chart (Recharts) | Nivo, Victory | Not available — decided in Phase 1, CSS vars already wired |
| Intl.NumberFormat | numeral.js, accounting.js | No new deps needed; Intl is sufficient for EUR/de-DE |
| next/link for CTAs | router.push | `next/link` is preferred for static navigations; `router.push` for programmatic |

**Installation:** No new packages needed. Phase 2 uses only what Phase 1 installed.

---

## Architecture Patterns

### Recommended Project Structure

```
web-app/src/
├── app/(app)/home/
│   └── page.tsx                      # Dashboard page — 'use client' — composed from widgets below
├── components/dashboard/
│   ├── welcome-card.tsx              # DASH-01: user name + total spent this month
│   ├── summary-cards.tsx             # DASH-02: 4 metric cards with color coding
│   ├── spending-pie-chart.tsx        # DASH-03: top-5 category pie chart
│   ├── trend-line-chart.tsx          # DASH-04: 6-month trend line chart
│   ├── recent-transactions.tsx       # DASH-05: last 10 transactions + View All link
│   └── insights-callout.tsx          # DASH-06/07/08: AI highlights + CTAs
├── types/
│   └── analytics.ts                  # ADD narrow sub-interfaces (DashboardSpending, etc.)
```

### Pattern 1: Narrow Sub-Interfaces for DashboardResponse

**What:** Define concrete TypeScript interfaces matching the backend `financial.py` return shapes. Cast in `useDashboardSummary` so all consumers are typed.

**When to use:** Any time a `Record<string, unknown>` field from Phase 1 needs to be consumed by a component.

**Backend source of truth (from `server/app/tools/financial.py`):**

```typescript
// Add to web-app/src/types/analytics.ts

// From get_spending_summary() — dashboard.spending
export interface DashboardSpendingStat {
  month: string        // "2026-02" format
  total_expense: number
  total_income: number
  net: number
}

export interface DashboardSpending {
  overview: {
    stats: DashboardSpendingStat[]
    income_vs_expenses: Record<string, unknown>[]
  }
  recent_trend: {
    last_3_months: DashboardSpendingStat[]
    burn_rate: Record<string, unknown>[]
  }
  date_range: { start: string | null; end: string | null; total_days: number }
}

// From get_category_insights() — dashboard.categories
export interface DashboardCategoryItem {
  category: string
  total_amount: number
  transaction_count: number
  percentage: number
}

export interface DashboardCategories {
  top_categories: DashboardCategoryItem[]
  frequency_vs_impact: Record<string, unknown>[]
  confidence_weighted: Record<string, unknown>[]
  category_trends: { top_growing: Record<string, unknown>[]; top_declining: Record<string, unknown>[] }
}

// From get_recurring_insights() — dashboard.recurring
export interface DashboardRecurring {
  recurring_summary: Record<string, unknown>[]
  monthly_recurring_costs: Array<{ merchant: string; estimated_monthly_cost: number }>
  recurring_by_category: Record<string, unknown>[]
  hidden_subscriptions: Record<string, unknown>[]
  insights: {
    total_recurring_percentage: number
    total_hidden_subscriptions: number
    top_recurring_merchant: string | null
  }
}

// From get_trend_insights() — dashboard.trends
export interface DashboardTrendPoint {
  month: string         // "2026-02" format
  total_expense: number
  total_income: number
  expense_mom_growth: number | null
}

export interface DashboardTrends {
  monthly_trend: DashboardTrendPoint[]
  year_comparison: Record<string, unknown>[]
  burn_rate: Record<string, unknown>[]
  top_growing: Record<string, unknown>[]
  top_declining: Record<string, unknown>[]
  insights: { latest_mom_growth: number | null }
}

// Narrow DashboardResponse — replace Record<string, unknown> fields
export interface DashboardResponse {
  spending: DashboardSpending
  categories: DashboardCategories
  recurring: DashboardRecurring
  trends: DashboardTrends
  generated_at: string
}
```

### Pattern 2: Per-Widget ErrorBoundary Isolation

**What:** Wrap each dashboard widget in its own `ErrorBoundary` so a failed insights fetch doesn't crash the charts, and a charts error doesn't hide the transactions widget.

**When to use:** Every data-fetching widget on the dashboard.

```tsx
// Source: existing web-app/src/components/shared/error-boundary.tsx
import { ErrorBoundary } from '@/components/shared/error-boundary'
import { CardSkeleton } from '@/components/shared/skeletons/card-skeleton'

// In page.tsx:
<ErrorBoundary fallback={<CardSkeleton count={4} />}>
  <SummaryCards />
</ErrorBoundary>
```

### Pattern 3: Currency Formatting

**What:** Parse string amounts and format with de-DE EUR locale. Create a shared utility.

**When to use:** Any component rendering `amount`, `total_expense`, `total_income`, `estimated_monthly_cost`.

```typescript
// Source: STATE.md decision — EUR (de-DE locale) is default throughout
// Add to web-app/src/lib/utils.ts or a dedicated web-app/src/lib/format.ts

export function formatCurrency(value: number | string, currency = 'EUR', locale = 'de-DE'): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  return new Intl.NumberFormat(locale, { style: 'currency', currency }).format(num)
}
```

### Pattern 4: Color-Coded Summary Cards

**What:** Use Tailwind utility classes with `cn()` for conditional green/red coloring based on thresholds. Do NOT use inline styles or hardcoded hex values.

**When to use:** DASH-02 summary cards.

```tsx
// Source: globals.css tokens — primary is teal (oklch 0.60 0.10 185), destructive is red
import { cn } from '@/lib/utils'

// Green = positive/healthy; Red = overspend
const valueClass = cn(
  'text-2xl font-bold',
  isOverspend ? 'text-destructive' : 'text-primary'
)
```

**Note:** `--destructive` maps to red (oklch 0.577 0.245 27.325) and `--primary` maps to teal — these match the DASH-02 color requirements without hardcoding.

### Pattern 5: Clerk User Name Access

**What:** Use `useUser()` hook from `@clerk/nextjs` to get the user's first name for the welcome card.

**When to use:** DASH-01 welcome card.

```tsx
'use client'
import { useUser } from '@clerk/nextjs'

export function WelcomeCard({ totalSpent }: { totalSpent: number }) {
  const { user } = useUser()
  return (
    <div>
      <h1>Welcome back, {user?.firstName ?? 'there'}</h1>
      <p>You have spent {formatCurrency(totalSpent)} this month.</p>
    </div>
  )
}
```

### Pattern 6: Recent Transactions Widget (limit=10)

**What:** Call `useTransactions` with `limit: 10` and `sort_by: 'date'` / `sort_order: 'desc'`. Display in a simple list (not a full table — that's Phase 3).

**When to use:** DASH-05.

```tsx
// Source: web-app/src/hooks/use-transactions.ts (Phase 1)
const { data, isLoading } = useTransactions({ sort_by: 'date', sort_order: 'desc' }, 0)
// data.items.slice(0, 10) for the widget
```

**Note:** The hook hardcodes `limit: 25` internally. Either pass `limit: 10` as a filter or slice `data.items` to 10. Slicing is simpler for a display widget; passing `limit: 10` as a filter is more efficient (avoids fetching 25 rows just to show 10). Use the filter approach.

### Anti-Patterns to Avoid

- **Re-implementing useTransactions for the widget:** The hook in Phase 1 accepts filters. Just call `useTransactions({ sort_by: 'date', sort_order: 'desc', limit: 10 }, 0)`.
- **Using `hsl(var(--chart-N))` for chart colors:** STATE.md is explicit — use `var(--chart-N)` directly. The Tailwind v4 OKLCH tokens break when wrapped in `hsl()`.
- **Parsing amount to float for storage:** Always parse at render time only. Never pass a float into React Query's `queryKey` or store a parsed float in state.
- **Fetching insights and transactions in the same query:** Keep them separate hooks with separate stale times (insights=10min, transactions=30s).
- **Blocking the entire page on dashboard data:** Each widget should independently manage its loading/error state. Do not hoist all three queries to the page level and wait for all three before rendering anything.
- **Using `router.push` for CTA navigation:** Use `next/link` for "Upload CSV" and "View Insights" — they are static navigation targets.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Pie chart with legend and percentages | Custom SVG pie | `PieChart` wrapper (Phase 1) with `showLegend=true` | Already built, wired to shadcn ChartContainer |
| Line chart with hover tooltips | Custom SVG line | `LineChart` wrapper (Phase 1) | ChartTooltip is already configured |
| Loading skeleton for cards | Div with pulse animations | `CardSkeleton` (Phase 1, `count=4`) | Already matches card dimensions |
| Loading skeleton for charts | Custom shimmer | `ChartSkeleton` (Phase 1, `variant='pie'` or `'line'`) | Correct visual shapes already defined |
| Loading skeleton for transactions | Custom row shimmer | `TableSkeleton` (Phase 1, `rows=10, columns=4`) | Already parameterizable |
| Error UI | Inline try/catch + conditional render | `ErrorBoundary` (Phase 1) | Catches render errors, shows toast |
| Authentication-gated fetch | Manual token storage | `useAuth().getToken()` inside `queryFn` | Phase 1 pattern — token per-request |
| Currency formatting | Custom formatter | `Intl.NumberFormat` with `de-DE`/`EUR` | No dependency, handles edge cases |

**Key insight:** Phase 1 was designed specifically to produce the primitives Phase 2 consumes. The dashboard page is primarily a composition exercise, not a build exercise.

---

## Common Pitfalls

### Pitfall 1: `DashboardResponse` Field Narrowing Gap

**What goes wrong:** Component tries to access `data.spending.overview.stats[0].total_expense` but TypeScript sees `Record<string, unknown>`, causing either a compile error or requiring unsafe casts throughout widget code.

**Why it happens:** Phase 1 deliberately deferred narrowing (documented in STATE.md: "AnalyticsResponse.data typed as Record<string, unknown> — narrowing deferred to Phase 2/4").

**How to avoid:** Add the narrow sub-interfaces to `types/analytics.ts` FIRST (Plan 1 of Phase 2). Update `DashboardResponse` to use the narrow types. The hook `useDashboardSummary` will automatically return the narrow type.

**Warning signs:** Code that does `(data.spending as any).overview` or `Object.keys(data.spending)` instead of direct property access.

### Pitfall 2: Chart Color Breakage

**What goes wrong:** Chart renders with wrong colors or no colors — fills appear black or transparent.

**Why it happens:** Using `hsl(var(--chart-N))` instead of `var(--chart-N)` directly. Tailwind v4 defines `--chart-N` in OKLCH format, and wrapping it in `hsl()` fails silently.

**How to avoid:** The existing `PieChart` and `LineChart` wrappers already use `var(--chart-${(index % 5) + 1})` — use them as-is. If building a custom chart component, copy the same pattern.

**Warning signs:** Charts render but all bars/slices are the same color or are missing entirely.

### Pitfall 3: Amount Precision Loss

**What goes wrong:** Displaying `"1234.567"` → `1234.5670000000001` after `parseFloat` or `Number()` conversion.

**Why it happens:** JavaScript IEEE 754 float. Financial amounts from the API are Python Decimal serialized as strings.

**How to avoid:** Parse only at render time. Use `parseFloat(amount).toFixed(2)` or pass directly to `Intl.NumberFormat` which handles rounding correctly: `new Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' }).format(parseFloat(amount))`.

**Warning signs:** Amount shows more than 2 decimal places or unexpected rounding.

### Pitfall 4: Insights Empty State

**What goes wrong:** `useInsights()` returns `data.insights = []` (empty array) when no insights have been generated yet. Component tries to access `data.insights[0].summary` and throws.

**Why it happens:** First-time users with no generated insights. The backend returns a valid `InsightsResponse` with an empty `insights` array.

**How to avoid:** Always guard: `const topInsights = data?.insights?.slice(0, 2) ?? []`. Render an empty/CTA state when `topInsights.length === 0`.

**Warning signs:** Runtime error `Cannot read properties of undefined (reading 'summary')` in the insights callout.

### Pitfall 5: Monthly Trend Data is Last 12 Months, Not 6

**What goes wrong:** The trend line chart shows 12 months of data when the requirement is 6 months.

**Why it happens:** `get_trend_insights` returns `monthly_trend.tail(12)` from the backend. The dashboard needs to slice to 6.

**How to avoid:** In `TrendLineChart`, use `.slice(-6)` on `trends.monthly_trend` before passing to `LineChart`.

**Warning signs:** Chart shows too many data points; x-axis labels extend past 6 months.

### Pitfall 6: Upload Route Does Not Exist

**What goes wrong:** Clicking "Upload CSV" navigates to a 404 because `/upload` or `/csv-upload` route doesn't exist yet.

**Why it happens:** CSV upload is a later phase.

**How to avoid:** Either stub the route (`app/(app)/upload/page.tsx` with a placeholder) as part of Phase 2, or disable the button and show a tooltip ("Coming soon"). Given DASH-07 says "can click to reach the upload flow", a stub page is the correct choice.

**Warning signs:** Link points to `/upload` but the route file doesn't exist — Next.js renders the not-found page.

---

## Code Examples

Verified patterns from project source:

### Composing the Dashboard Page

```tsx
// web-app/src/app/(app)/home/page.tsx
'use client'

import { ErrorBoundary } from '@/components/shared/error-boundary'
import { CardSkeleton } from '@/components/shared/skeletons/card-skeleton'
import { ChartSkeleton } from '@/components/shared/skeletons/chart-skeleton'
import { WelcomeCard } from '@/components/dashboard/welcome-card'
import { SummaryCards } from '@/components/dashboard/summary-cards'
import { SpendingPieChart } from '@/components/dashboard/spending-pie-chart'
import { TrendLineChart } from '@/components/dashboard/trend-line-chart'
import { RecentTransactions } from '@/components/dashboard/recent-transactions'
import { InsightsCallout } from '@/components/dashboard/insights-callout'

export default function HomePage() {
  return (
    <div className="space-y-6">
      <ErrorBoundary>
        <WelcomeCard />
      </ErrorBoundary>

      <ErrorBoundary fallback={<CardSkeleton count={4} />}>
        <SummaryCards />
      </ErrorBoundary>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ErrorBoundary fallback={<ChartSkeleton variant="pie" />}>
          <SpendingPieChart />
        </ErrorBoundary>
        <ErrorBoundary fallback={<ChartSkeleton variant="line" />}>
          <TrendLineChart />
        </ErrorBoundary>
      </div>

      <ErrorBoundary>
        <RecentTransactions />
      </ErrorBoundary>

      <ErrorBoundary>
        <InsightsCallout />
      </ErrorBoundary>
    </div>
  )
}
```

### useDashboardSummary with Narrow Types

```tsx
// web-app/src/hooks/use-dashboard-summary.ts — after types are narrowed in Plan 1
// The hook signature stays the same; TypeScript automatically infers the narrow return type
// because DashboardResponse is updated in types/analytics.ts
import type { DashboardResponse } from '@/types/analytics'  // now uses narrow types

export function useDashboardSummary(filters: AnalyticsFilters = {}) {
  const { getToken } = useAuth()
  return useQuery<DashboardResponse>({
    queryKey: ['dashboard', filters],
    queryFn: async () => {
      const token = await getToken()
      return fetchDashboard(token, filters)
    },
    staleTime: 2 * 60 * 1000,
  })
}
```

### PieChart for Top 5 Categories

```tsx
// web-app/src/components/dashboard/spending-pie-chart.tsx
'use client'
import { useDashboardSummary } from '@/hooks/use-dashboard-summary'
import { PieChart } from '@/components/shared/charts/pie-chart'
import { ChartSkeleton } from '@/components/shared/skeletons/chart-skeleton'
import type { ChartConfig } from '@/components/ui/chart'

export function SpendingPieChart() {
  const { data, isLoading } = useDashboardSummary()
  if (isLoading) return <ChartSkeleton variant="pie" />

  const top5 = data?.categories.top_categories.slice(0, 5) ?? []
  const chartData = top5.map(c => ({ label: c.category, value: c.total_amount }))
  const config: ChartConfig = Object.fromEntries(
    top5.map((c, i) => [c.category, { label: c.category, color: `var(--chart-${(i % 5) + 1})` }])
  )

  return <PieChart data={chartData} config={config} showLegend />
}
```

### TrendLineChart (6-month slice)

```tsx
// web-app/src/components/dashboard/trend-line-chart.tsx
'use client'
import { useDashboardSummary } from '@/hooks/use-dashboard-summary'
import { LineChart } from '@/components/shared/charts/line-chart'
import { ChartSkeleton } from '@/components/shared/skeletons/chart-skeleton'

export function TrendLineChart() {
  const { data, isLoading } = useDashboardSummary()
  if (isLoading) return <ChartSkeleton variant="line" />

  // Backend returns up to 12 months; dashboard shows 6
  const last6 = (data?.trends.monthly_trend ?? []).slice(-6)
  const config = {
    total_expense: { label: 'Expenses', color: 'var(--chart-1)' },
  }

  return (
    <LineChart
      data={last6}
      series={[{ dataKey: 'total_expense', color: 'var(--chart-1)', label: 'Expenses' }]}
      xAxisKey="month"
      config={config}
    />
  )
}
```

### Currency Formatter Utility

```typescript
// web-app/src/lib/format.ts (new file)
export function formatCurrency(
  value: number | string,
  currency = 'EUR',
  locale = 'de-DE'
): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '—'
  return new Intl.NumberFormat(locale, { style: 'currency', currency }).format(num)
}
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `hsl(var(--chart-N))` | `var(--chart-N)` directly | Required for Tailwind v4 OKLCH tokens — established in Phase 1 |
| `amount: number` | `amount: string` | Financial precision — Python Decimal serializes as JSON string |
| `react-error-boundary` package | Custom `ErrorBoundary` class component | Zero-dependency, established in Phase 1 (Plan 02) |
| Default `gcTime` | `gcTime: 30 * 60 * 1000` for insights | Keeps expensive insight data across navigation |

**Note on FOUND-03 status:** STATE.md shows FOUND-03 (React Query hooks) as pending but the hook files exist on disk (`use-dashboard-summary.ts`, `use-transactions.ts`, `use-insights.ts`). Phase 2 can use all hooks directly — FOUND-03 completion likely needs a requirements checkbox update only.

---

## Open Questions

1. **Upload CSV route path**
   - What we know: DASH-07 requires navigating to "the upload flow"; no upload route exists yet
   - What's unclear: Is the CSV upload phase already planned and what route will it use? The sidebar nav has `/home`, `/transactions`, `/stats` — no `/upload`
   - Recommendation: Create `app/(app)/upload/page.tsx` as a stub ("Coming soon") within Phase 2. This satisfies DASH-07 without blocking Phase 3.

2. **Insights route: `/stats` vs `/insights`**
   - What we know: The sidebar nav has `/stats`, but DASH-08 says "navigate to Insights page". `app/(app)/stats/page.tsx` exists as a stub.
   - What's unclear: Should Phase 2 rename `/stats` to `/insights` or leave it as-is?
   - Recommendation: Either rename the route to `/insights` during Phase 2 (preferred — matches the requirement language and phase 5 naming), or leave it as `/stats` and update DASH-08 navigation accordingly. Renaming is low-cost at this stage.

3. **Savings Goal data source**
   - What we know: DASH-02 lists "Savings Goal Progress" as one of the 4 summary cards. `DashboardResponse` has no `savings_goal` field — the backend does not expose a savings target.
   - What's unclear: Where does the goal threshold come from? There is no budget API (STATE.md: "Budgets page is placeholder only — no backend budget API available").
   - Recommendation: Display "Savings Goal" card with `DashboardResponse.spending.overview.stats` for total income/expense, and compute savings as `income - expense`. No user-set goal threshold is available — show net savings position rather than progress-toward-goal.

4. **Remaining Budget data source**
   - What we know: DASH-02 also lists "Remaining Budget" as a summary card. No budget API exists.
   - What's unclear: What denominator to use for "remaining"?
   - Recommendation: Same approach as Savings Goal — derive from `total_income - total_expense` for the current month. Label as "Net Balance" or "Cash Flow" if no budget target is set, or render with a dashed/placeholder state to signal the feature is coming.

---

## Sources

### Primary (HIGH confidence)
- `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/src/` — all Phase 1 source files read directly
- `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/tools/financial.py` — authoritative backend data shapes
- `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/schemas/analytics.py` — Pydantic schema confirming field names
- `/Users/tizianoiacovelli/projects/personal-finance-app/.planning/STATE.md` — accumulated decisions (EUR locale, chart color pattern, string amounts, FOUND-03 deferral)
- `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/package.json` — exact library versions confirmed

### Secondary (MEDIUM confidence)
- Clerk `useUser()` hook API — standard Clerk Next.js pattern; `user.firstName` is standard Clerk User object field

### Tertiary (LOW confidence)
- None — all findings grounded in project source files

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — confirmed from package.json; all libraries already installed
- Architecture: HIGH — confirmed from Phase 1 source; composition is the only task
- Type narrowing shapes: HIGH — read directly from backend `financial.py` return values
- Pitfalls: HIGH — derived from Phase 1 decisions documented in STATE.md and SUMMARY files
- Open questions (budget/savings): MEDIUM — no backend endpoint; recommendation is a pragmatic workaround

**Research date:** 2026-02-27
**Valid until:** 2026-03-29 (30 days — stable stack; backend is finalized)
