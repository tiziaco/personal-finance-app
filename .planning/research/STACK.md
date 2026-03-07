# Stack Research

**Domain:** Personal finance dashboard frontend (Next.js, charts, data tables)
**Researched:** 2026-02-26
**Confidence:** HIGH for existing stack decisions; MEDIUM for react-charts integration patterns

---

## Current Stack (Already Installed)

This is an additive milestone. The stack is largely fixed. The table below documents what exists and confirms it is the right choice.

| Technology | Version | Purpose | Status |
|------------|---------|---------|--------|
| Next.js | 16.1.6 | React framework, App Router, SSR/SSG | Installed, finalized |
| React | 19.2.4 | UI component model | Installed, finalized |
| TypeScript | 5 | Static typing | Installed, finalized |
| Tailwind CSS | 4 (latest) | Utility CSS | Installed, Tailwind v4 CSS-first config |
| shadcn/ui | 3.8.5 (CLI) | Component library | Installed, Tailwind v4 + React 19 compatible |
| @tanstack/react-query | 5.90.21 | Server state, data fetching, caching | Installed, QueryProvider configured |
| @tanstack/react-table | 8.21.3 | Headless table logic for Transactions page | Installed |
| @clerk/nextjs | 6.38.1 | Auth provider, JWT tokens | Installed, middleware protecting all routes |
| lucide-react | 0.575.0 | Icon library | Installed |
| sonner | 2.0.7 | Toast notifications | Installed, Toaster in root layout |
| zod | 4.3.6 | Schema validation | Installed |
| next-themes | 0.4.6 | Dark mode switching | Installed, ThemeProvider in root layout |
| tw-animate-css | 1.4.0 | Animation utilities (replaces tailwindcss-animate) | Installed |

---

## Charts Library: Critical Decision

**The user specified TanStack React Charts (react-charts.tanstack.com). Verified facts about this library:**

### What react-charts IS

- Package: `react-charts` (NOT `@tanstack/react-charts` — that package does not exist on npm)
- Install: `npm install react-charts@beta`
- Latest beta: `3.0.0-beta.57` (published November 2023; also on `beta` dist-tag)
- Older stable: `2.0.0-beta.7` (published 6 years ago, do not use)
- Peer deps: React >= 16 (compatible with React 19)
- Chart types: **X/Y charts only** — line, area, bar, column, bubble

### What react-charts IS NOT

- **Does NOT support pie charts.** This is a deliberate design decision by the maintainer, not an omission. The library documentation explicitly states it "purposefully does not have support for pie charts, radar charts, or other circular nonsense." This is non-negotiable — there is no workaround or plugin.
- Not actively maintained: last release was November 2023, maintainer engagement is minimal, repo has open issues without responses. The library is pre-1.0 and its roadmap is unclear.

### Impact on Dashboard Requirements

The Dashboard page in PROJECT.md requires a pie chart (spending breakdown by category). Since react-charts cannot render pie charts, one of these two approaches is required:

**Option A (Recommended): Use shadcn/ui Chart (Recharts) for pie charts only.**
shadcn/ui ships a built-in `chart` component backed by Recharts. Recharts has full pie chart support with shadcn-native styling via CSS variables. Use react-charts for all X/Y charts (line, bar, area) and shadcn/ui Chart for pie charts. Both consume the same CSS variable design tokens (`--chart-1` through `--chart-5` are already defined in `globals.css`).

**Option B: Replace react-charts with shadcn/ui Chart (Recharts) for all charts.**
If the user is open to reconsidering the constraint, Recharts via shadcn/ui is the cleaner choice — it supports all required chart types (pie, line, bar, area), is actively maintained, integrates natively with the existing shadcn design system, and avoids SSR/dynamic-import complexity. However, this contradicts the explicit user requirement.

**Decision for phases: Implement Option A** unless user confirms preference for Option B. Flag this explicitly in the roadmap.

---

## Recommended Stack (New Additions Only)

### Core Libraries to Install

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| react-charts | `@beta` (3.0.0-beta.57) | Line/bar/area charts — NOT pie charts | User-specified; handles X/Y financial time series well |
| recharts | `^2.15.0` (via shadcn CLI) | Pie chart only, via `shadcn add chart` | Only way to get pie charts in this stack; shadcn/ui Chart wraps Recharts |

**Install command:**
```bash
# In /web-app
npm install react-charts@beta
npx shadcn add chart
```

Do NOT install recharts directly — add it via the shadcn CLI so the wrapper component is generated correctly.

### Supporting Libraries Already Available (No Action Needed)

| Library | Version | What it Enables |
|---------|---------|-----------------|
| @tanstack/react-table | 8.21.3 | Transactions page table with sort/filter/pagination |
| sonner | 2.0.7 | All toast notifications (already in root layout) |
| next-themes | 0.4.6 | Dark mode (already in root layout) |

---

## Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| @tanstack/react-query-devtools | 5.91.3 | Query inspector in dev mode | Already in QueryProvider, gated by `isDevelopment` |
| ESLint 9 + eslint-config-next | Linting | Already configured in `eslint.config.mjs` |

---

## Configuration Patterns

### Pattern 1: API Calls with Clerk Auth (ESTABLISHED PATTERN — follow this)

The codebase uses a consistent 3-layer pattern: API function → custom hook → component.

```typescript
// Layer 1: src/lib/api/transactions.ts — pure fetch function
export async function fetchTransactions(token: string | null): Promise<TransactionsResponse> {
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/transactions`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: 'no-store',
  })
  if (!response.ok) throw new Error(`Failed: ${response.status}`)
  return response.json()
}

// Layer 2: src/hooks/use-transactions.ts — React Query hook
"use client"
import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@clerk/nextjs'

export function useTransactions() {
  const { getToken } = useAuth()
  return useQuery({
    queryKey: ['transactions'],
    queryFn: async () => {
      const token = await getToken()
      return fetchTransactions(token)
    },
  })
}

// Layer 3: Component uses the hook
```

All API hooks are `"use client"` because they use `useAuth()` from Clerk. The established `staleTime: 60s, gcTime: 5min, refetchOnWindowFocus: false, retry: 1` defaults from QueryProvider apply globally — override per-query only when needed.

### Pattern 2: react-charts SSR Handling (CRITICAL — must follow this)

react-charts uses D3 ESM-only packages that cannot run in Next.js server context. Every component that imports react-charts MUST be wrapped in `dynamic` with `ssr: false`.

```typescript
// src/components/charts/line-chart.tsx
"use client"
import dynamic from 'next/dynamic'
import type { Chart as ChartType } from 'react-charts'

// Dynamic import prevents SSR, which would crash with "window is not defined"
const Chart = dynamic(
  () => import('react-charts').then((mod) => mod.Chart),
  {
    ssr: false,
    loading: () => <ChartSkeleton />, // show skeleton during client hydration
  }
) as typeof ChartType
```

Do NOT use `esmExternals: 'loose'` in next.config.ts — this causes `React.createContext is not a function` errors (confirmed in GitHub issue #304).

### Pattern 3: react-charts Axis Configuration

```typescript
import { useMemo } from 'react'
import type { AxisOptions } from 'react-charts'

type SpendingDatum = { date: Date; amount: number }

// Always memoize axis definitions — re-creating them on every render causes jitter
const primaryAxis = useMemo(
  (): AxisOptions<SpendingDatum> => ({
    getValue: datum => datum.date, // time scale inferred automatically
  }),
  []
)

const secondaryAxes = useMemo(
  (): AxisOptions<SpendingDatum>[] => [{
    getValue: datum => datum.amount,
    elementType: 'line', // or 'bar', 'area'
  }],
  []
)
```

### Pattern 4: shadcn/ui Chart (Recharts) for Pie Charts

After running `npx shadcn add chart`, the chart component uses CSS variables from `globals.css`. The project already defines `--chart-1` through `--chart-5` in both light and dark themes (teal/cyan scale in OKLCH).

```typescript
// Pie chart — uses shadcn/ui Chart + Recharts
import { ChartContainer, ChartTooltip, ChartTooltipContent } from "@/components/ui/chart"
import { Pie, PieChart } from "recharts"

const chartConfig = {
  food: { label: "Food", color: "var(--chart-1)" },
  transport: { label: "Transport", color: "var(--chart-2)" },
  // etc.
}

// Do NOT wrap in hsl() — globals.css already defines colors as OKLCH values directly
// shadcn v4 pattern: colors are raw values, not hsl() wrappers
```

### Pattern 5: Tailwind CSS 4 with shadcn/ui (Already Configured — No Action Needed)

The project already has the correct Tailwind v4 setup:
- `@import "tailwindcss"` in globals.css (CSS-first config, no tailwind.config.js content needed)
- `@import "tw-animate-css"` (replaces tailwindcss-animate)
- `@import "shadcn/tailwind.css"` (injects shadcn base styles)
- `@theme inline { ... }` block maps CSS variables to Tailwind tokens
- OKLCH color values throughout (Tailwind v4 uses OKLCH natively)

The `tailwind.config.ts` is minimal (content paths only) — this is correct for v4. Do not add theme extensions there; add them to `globals.css` under `@theme inline`.

**Tailwind v4 class changes to know:**
- `size-*` replaces `w-* h-*` combinations (e.g., `size-4` instead of `w-4 h-4`)
- `inset-*` replaces positional combinations
- No `@apply` for complex utilities — use direct class composition

---

## Installation

```bash
# Navigate to web-app directory
cd web-app

# Add react-charts (beta tag = v3.0.0-beta.57, the latest beta)
npm install react-charts@beta

# Add shadcn chart component (installs recharts as peer dep)
npx shadcn add chart

# Verify no peer dep conflicts
npm ls react recharts
```

**Expected after install:**
- `react-charts@3.0.0-beta.57` in dependencies
- `recharts@^2.x` as peer dep pulled in by shadcn chart
- `src/components/ui/chart.tsx` generated by shadcn CLI

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| react-charts@beta for X/Y charts | recharts directly | If user drops react-charts requirement — recharts covers all chart types, actively maintained, zero SSR friction |
| shadcn/ui Chart (Recharts) for pie | D3.js pie directly | If custom donut with animations beyond Recharts capabilities |
| @tanstack/react-table | Custom table | Never for this project — react-table already installed and handles all table requirements |
| React Query useQuery | SWR | SWR is viable but react-query is already configured and in use |
| next/dynamic ssr:false for charts | useEffect + state flag | Both work; dynamic import is cleaner and produces proper Suspense boundaries |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `react-charts@latest` (v2.0.0-beta.7) | Published 6 years ago, does not work with React 19 | `react-charts@beta` (3.0.0-beta.57) |
| `@tanstack/react-charts` | This package name does not exist on npm — the correct scope is just `react-charts` | `react-charts` |
| `recharts` direct import for all charts | Contradicts user requirement for TanStack React Charts | react-charts for X/Y, recharts via shadcn for pie only |
| `tailwindcss-animate` | Deprecated in shadcn/ui v4 setup; already replaced by tw-animate-css in this project | `tw-animate-css` (already installed) |
| `next.config.ts` `esmExternals: 'loose'` | Causes `React.createContext is not a function` with react-charts | `dynamic(() => import('react-charts'), { ssr: false })` instead |
| Server Components for chart pages | Charts require browser APIs (ResizeObserver, DOM measurement); SSR will throw | Always `"use client"` for any component importing react-charts |

---

## Stack Patterns by Page

**Dashboard page:**
- Summary cards: shadcn `Card`, `Badge` — no new installs
- Pie chart (spending by category): shadcn Chart (Recharts) via `npx shadcn add chart`
- Line chart (spending over time): react-charts, dynamic import ssr:false
- Recent transactions widget: shadcn `Table` via `npx shadcn add table`
- AI insights callout: shadcn `Card` + `Badge`
- Skeleton loading: shadcn `Skeleton` (already installed)

**Transactions page:**
- Filterable table: @tanstack/react-table (already installed) + shadcn `Table`, `Input`, `Select`, `Badge`
- Category edit modal: shadcn `Dialog` (already installed) + `Select`
- Bulk actions: `data-table-bulk-actions.tsx` already exists in components/ui/
- Pagination: shadcn `Button` group or custom pagination component

**Analytics page:**
- Tab navigation: shadcn `Tabs` via `npx shadcn add tabs`
- Bar chart (spending by category): react-charts `elementType: 'bar'`
- Line chart (income vs expenses, MoM): react-charts `elementType: 'line'`
- All charts: dynamic import ssr:false pattern

**Insights page:**
- Insight cards: shadcn `Card` + `Badge`
- Generate button: shadcn `Button` with loading state (sonner for feedback)
- Savings tracker: shadcn `Progress` via `npx shadcn add progress`

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| react-charts@3.0.0-beta.57 | React >= 16 (confirmed React 19 via peer dep spec) | Must use `dynamic(..., {ssr: false})` in Next.js; beta quality, test each chart type |
| @tanstack/react-query@5.90.21 | React 19, Next.js App Router | Fully streaming-compatible; QueryProvider already marked `"use client"` |
| shadcn/ui@3.8.5 | Tailwind CSS 4, React 19 | Already installed; all components updated for v4; uses OKLCH colors |
| @clerk/nextjs@6.38.1 | Next.js 16, React 19 | Middleware at `src/proxy.ts`; `useAuth()` only in client components |
| recharts (via shadcn chart) | React 19 | Pull in via `npx shadcn add chart`; do not pin version manually |
| next-themes@0.4.6 | Next.js App Router | ThemeProvider already in root layout with `attribute="class"` |

---

## Sources

- [react-charts npm registry](https://www.npmjs.com/package/react-charts) — version confirmation (3.0.0-beta.57), dist-tags verified via `npm show`
- [TanStack react-charts installation docs](https://react-charts.tanstack.com/docs/installation) — install command: `npm install react-charts@beta`
- [TanStack react-charts GitHub issue #324](https://github.com/TanStack/react-charts/issues/324) — Next.js dynamic import `ssr: false` pattern confirmed by community (MEDIUM confidence)
- [TanStack react-charts pie chart discussion #283](https://github.com/TanStack/react-charts/discussions/283) — confirmed: pie charts deliberately unsupported (HIGH confidence)
- [TanStack react-charts issue #352](https://github.com/TanStack/react-charts/issues/352) — maintenance status; last release November 2023 (HIGH confidence)
- [shadcn/ui Tailwind v4 docs](https://ui.shadcn.com/docs/tailwind-v4) — migration patterns, OKLCH colors, tw-animate-css (HIGH confidence)
- [shadcn/ui pie chart examples](https://ui.shadcn.com/charts/pie) — Recharts-backed pie component confirmed (HIGH confidence)
- Existing codebase: `package.json`, `globals.css`, `components.json`, `query-provider.tsx`, `use-server-status.ts` — all patterns confirmed from source (HIGH confidence)

---

*Stack research for: Personal finance dashboard frontend (Next.js 16 + React 19 additive milestone)*
*Researched: 2026-02-26*
