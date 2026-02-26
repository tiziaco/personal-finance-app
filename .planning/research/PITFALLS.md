# Pitfalls Research

**Domain:** Next.js 16 App Router personal finance dashboard with TanStack Charts, shadcn/ui, Tailwind 4, React Query, Clerk
**Researched:** 2026-02-26
**Confidence:** HIGH (critical pitfalls verified against official docs, GitHub issues, and Vercel engineering blog)

---

## Critical Pitfalls

### Pitfall 1: TanStack React Charts Crashes on Server — Missing `dynamic()` Wrapper

**What goes wrong:**
Any component that imports from `react-charts` will crash Next.js SSR with the error: `Module not found: ESM packages (d3-time-format) need to be imported. Use 'import' to reference the package instead.` The chart component renders on the server, Next.js tries to resolve D3 (an ESM-only library) as CJS, and the build fails.

Attempting to work around this with `esmExternals: 'loose'` in `next.config.js` surfaces a second error: `Error: React.createContext is not a function`.

**Why it happens:**
TanStack React Charts v3 depends on D3 libraries that have dropped CommonJS builds entirely. Next.js SSR defaults to CJS resolution. The incompatibility is at the module system level and cannot be fixed at the import site — only by skipping SSR entirely for chart components.

**How to avoid:**
Every chart component must be loaded with `next/dynamic` and `ssr: false`:

```typescript
// components/charts/LineChart.tsx
"use client";
import dynamic from "next/dynamic";

const Chart = dynamic(
  () => import("react-charts").then((mod) => mod.Chart),
  { ssr: false, loading: () => <ChartSkeleton /> }
);
```

Never import directly from `react-charts` in any file that is not gated behind `ssr: false`. Create a single shared wrapper in `components/charts/` that all pages consume. Also add `"use client"` at the top of every chart wrapper file.

**Warning signs:**
- Build error mentioning `d3-time-format` or `ESM packages`
- `React.createContext is not a function` in server logs
- Charts render fine in development but crash in `next build`

**Phase to address:** Dashboard page (Phase 1) — the first chart usage must establish this pattern correctly so it is not retrofitted later.

---

### Pitfall 2: TanStack Charts Enters Infinite Re-render Loop — Unstable Options References

**What goes wrong:**
The `Chart` component internally watches option references for equality. If `data`, `primaryAxis`, or `secondaryAxes` are constructed inline (not memoized), React considers them "changed" on every render, causing the chart to continuously re-initialize. This manifests as an infinite render loop, a frozen UI, or a browser tab that becomes unresponsive.

**Why it happens:**
React objects created inline (arrays, objects, functions) have new references every render. The chart component's change-detection assumes referential equality — the same contract as `useEffect` dependency arrays. Finance dashboards compound this risk because data flows through multiple transforms (raw API response → grouped by category → chart series format) before reaching the chart.

**How to avoid:**
Wrap every chart option in `useMemo` or `useCallback`. This is not optional — the official docs state it is "almost always necessary":

```typescript
const data = useMemo(
  () => transactions.map((t) => ({ primary: t.date, secondary: t.amount })),
  [transactions]
);

const primaryAxis = useMemo<AxisOptions<typeof data[number]>>(
  () => ({ getValue: (datum) => datum.primary }),
  []
);

const secondaryAxes = useMemo<AxisOptions<typeof data[number]>[]>(
  () => [{ getValue: (datum) => datum.secondary, elementType: "line" }],
  []
);
```

Never pass raw query results directly as chart `data`. Always derive chart data inside `useMemo` with the query result as the dependency.

**Warning signs:**
- Browser tab becomes unresponsive when navigating to a chart page
- React DevTools profiler shows the chart component mounting repeatedly without user interaction
- Memory usage climbs steadily on the analytics page

**Phase to address:** Dashboard page (Phase 1) for first chart; reinforced in Analytics page (Phase 3).

---

### Pitfall 3: QueryClient Created Outside `useState` — Cache Shared Across Requests

**What goes wrong:**
If `QueryClient` is instantiated at module scope (outside a component) in a client provider, it becomes a singleton shared across all server-rendered requests. User A's cached data leaks into User B's rendered HTML. In development this is invisible; in production with concurrent requests it causes data contamination.

**Why it happens:**
Developers copy patterns from Pages Router (where module-scope clients are safe) into App Router. The mental model hasn't caught up: in App Router, server rendering happens per-request, and module-level variables persist across requests on the server.

**How to avoid:**
Always create the `QueryClient` inside `useState` in the client provider, so each component tree gets its own instance:

```typescript
// app/providers.tsx
"use client";
import { useState } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 60 seconds — prevents double-fetch after SSR
          },
        },
      })
  );
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

For server-side prefetching in RSC, use React's `cache()` function to scope the instance per-request:

```typescript
import { cache } from "react";
const getQueryClient = cache(() => new QueryClient());
```

**Warning signs:**
- Users see each other's transaction data after navigating between pages
- Stale data from a previous user session appears after logout/login
- `queryClient` variable defined at the top of a file outside any function

**Phase to address:** Project setup / Provider configuration (before any data fetching is wired up).

---

### Pitfall 4: `staleTime: 0` Causes Double-Fetch After SSR Hydration

**What goes wrong:**
With the default `staleTime: 0`, TanStack Query considers all data stale the moment it hydrates on the client. If the server prefetched data via `dehydrate/HydrationBoundary`, the client immediately refetches it anyway, making the entire SSR prefetch wasted work. On the dashboard, this means every card fires a second network request right after the HTML loads.

**Why it happens:**
`staleTime: 0` is the safe default for client-only apps where you always want fresh data. It is the wrong default when the server has already fetched fresh data seconds ago. Developers don't think to change it during setup.

**How to avoid:**
Set a global `staleTime` of at least 60 seconds in the `QueryClient` default options (see Pitfall 3 code above). For finance data that doesn't change between server render and page load, 5 minutes is reasonable. For mutation-driven queries (e.g., after uploading a CSV), call `queryClient.invalidateQueries()` explicitly — don't rely on staleness to trigger refetch.

**Warning signs:**
- Network tab shows API calls firing immediately after the page finishes loading, duplicating the server-side prefetch calls
- Dashboard briefly shows skeleton states after content already appeared (SSR content replaced by loading state)

**Phase to address:** Provider configuration (Phase 0/setup), then enforced in every data-fetching hook.

---

### Pitfall 5: Tailwind 4 + shadcn/ui Color System Mismatch

**What goes wrong:**
Tailwind 4 migrated from HSL to OKLCH for theme colors and restructured how CSS variables are declared. If the project was initialized with shadcn/ui under Tailwind 4, but theme colors were manually set using the old HSL `hsl(var(--color))` pattern (common when copying from older tutorials), the chart color tokens and Tailwind utilities will not resolve correctly. Custom CSS variables declared inside `@layer base` also stop working as expected — they must move outside of `@layer`.

A secondary breakage: `tailwindcss-animate` (the old animation plugin) is deprecated. If it remains in `globals.css` as `@plugin "tailwindcss-animate"` after the upgrade, animations silently stop working.

**Why it happens:**
Documentation and tutorials for shadcn/ui are predominantly written against Tailwind 3. Copy-pasting from any guide older than mid-2024 introduces the old patterns. The migration codemod does not catch custom additions made to `globals.css`.

**How to avoid:**
- Do not wrap color values in `hsl()` manually — in Tailwind 4, theme variables already include it: use `var(--primary)` not `hsl(var(--primary))`
- Declare `:root` and `.dark` blocks outside of `@layer base`, under the `@theme inline` directive
- Replace `tailwindcss-animate` with `tw-animate-css`: remove the plugin import and add `@import "tw-animate-css";` at the top of `globals.css`
- Validate chart color tokens after setup: the `--chart-1` through `--chart-5` variables must resolve to valid colors in DevTools

**Warning signs:**
- Colors render as `transparent` or browser-default black despite being set
- Chart legend colors don't match chart bar/line colors
- Tailwind CLI outputs warnings about unknown color values
- Dark mode toggle changes some colors but not others

**Phase to address:** Design system setup (Phase 1, before building any components). Fix the globals.css/theme configuration once at the start.

---

### Pitfall 6: Suspense Boundary Placed Inside the Async Component — Doesn't Activate

**What goes wrong:**
A `<Suspense>` boundary placed as a wrapper *inside* the component that is doing the async work does not trigger. The page either hangs without showing a loading skeleton or throws an unhandled promise error. This is the most common structural mistake in App Router dashboards.

**Why it happens:**
Developers think of `<Suspense>` as an "I'm loading" indicator placed near the loading state. The mental model is backwards: Suspense must be placed *above* the suspended component in the tree — it cannot be the parent *within* the same component doing the fetch.

**How to avoid:**
Place `<Suspense>` in the parent layout or page file, wrapping the child component that fetches data:

```tsx
// app/(app)/home/page.tsx  — CORRECT
import { Suspense } from "react";
import { SummaryCards } from "@/components/dashboard/SummaryCards";
import { SummaryCardsSkeleton } from "@/components/dashboard/SummaryCardsSkeleton";

export default function DashboardPage() {
  return (
    <main>
      <Suspense fallback={<SummaryCardsSkeleton />}>
        <SummaryCards />  {/* This component does the async fetch */}
      </Suspense>
    </main>
  );
}
```

Never put `<Suspense>` inside `SummaryCards` as a wrapper around its own loading state — it won't fire.

**Warning signs:**
- Skeleton screens never appear; page loads blank then snaps to content
- `Error: Suspense boundary is not activated` in logs
- Loading fallback flashes only in development but not in production (React strict mode double-invokes)

**Phase to address:** Dashboard page (Phase 1) — establish the Suspense pattern in the first page so all subsequent pages copy the correct structure.

---

### Pitfall 7: AI Insight Generation — No Cooldown or In-Progress State Locks the Generate Button

**What goes wrong:**
The insights page has a "Generate Insights" button that triggers a long-running LLM workflow (confirmed slow in CONCERNS.md — no caching on the backend). Without a disabled/loading state and cooldown enforcement on the frontend, users can spam the button, firing multiple concurrent LLM requests. The backend has no batch-size protection for concurrent insight requests. This degrades performance for all users.

A second related failure: if the insights request takes 15–60 seconds and the user navigates away, React Query may attempt to update state on an unmounted component, producing console errors and stale cache corruption.

**Why it happens:**
Mutation states (`isPending`) are wired up for visual feedback but often not actually used to disable the trigger button. Developers test locally with fast mocks and never observe the multi-click scenario.

**How to avoid:**
- Gate the generate button behind `mutation.isPending` AND a client-side cooldown timer stored in `useState`
- On the backend, the insights endpoint already returns a cooldown field — read and enforce it in the UI
- Use React Query's `useMutation` with `onMutate`/`onSettled` lifecycle to manage optimistic disabled state
- Set a long `gcTime` on the insights query so navigating away doesn't immediately discard in-flight state

```typescript
const generateMutation = useMutation({
  mutationFn: generateInsights,
  onSuccess: () => queryClient.invalidateQueries({ queryKey: ["insights"] }),
});

<Button
  onClick={() => generateMutation.mutate()}
  disabled={generateMutation.isPending || cooldownActive}
>
  {generateMutation.isPending ? "Generating..." : "Generate Insights"}
</Button>
```

**Warning signs:**
- Network tab shows 3–5 simultaneous requests to `/api/insights/generate` after rapid button clicks
- Console warnings about "state update on unmounted component"
- Insight cards show different content each page visit (stale mutation racing with fresh data)

**Phase to address:** Insights page (Phase 4).

---

### Pitfall 8: Mobile Tables — Horizontal Overflow Without Explicit Scroll Container

**What goes wrong:**
The shadcn/ui `Table` component does not automatically enable horizontal scroll on overflow. On mobile, wide transaction tables (date, description, amount, category, actions columns) either clip content or push the layout, causing the entire page to scroll horizontally rather than just the table. This is a known GitHub issue in the shadcn/ui repo (issue #416).

A secondary issue: the shadcn/ui `ScrollArea` component has a known behavior where it creates whitespace equal to the overflowed content below the table when both horizontal and vertical scroll are enabled simultaneously.

**Why it happens:**
Developers test on desktop where the table fits. The overflow issue only surfaces at `<640px` viewport widths. `ScrollArea` is added as a fix but misconfigured with both axes active.

**How to avoid:**
Wrap the `Table` in a plain `div` with `overflow-x-auto` — not `ScrollArea` — for horizontal scroll. Use `ScrollArea` only for vertical scroll on fixed-height containers:

```tsx
<div className="w-full overflow-x-auto rounded-md border">
  <Table>
    {/* columns */}
  </Table>
</div>
```

Add `whitespace-nowrap` to cells that must not wrap (amounts, dates). For the transactions table specifically, consider a card-based layout on `sm:` breakpoint instead of a scrolling table — cards are more mobile-native for finance data.

**Warning signs:**
- Page has horizontal scroll on iOS Safari but not Chrome desktop
- Empty white space appears below the table equal to the table width minus viewport
- Table columns wrap text onto multiple lines at `<sm` breakpoints

**Phase to address:** Transactions page (Phase 2) — establish table mobile pattern here; reuse for analytics tables.

---

### Pitfall 9: `"use client"` Pushed Too High — Kills Server Component Benefits

**What goes wrong:**
Adding `"use client"` to a parent component (e.g., a layout wrapper, a card container, or a data provider) causes all components in that subtree to become client components, even ones that only render static content. This eliminates RSC streaming, increases JS bundle size, and blocks Suspense-based incremental loading.

In a finance dashboard, the typical failure mode is: a developer adds interactivity (a date range filter, a dropdown) to a container, adds `"use client"` to it, and inadvertently makes all the chart and card children client-side too.

**Why it happens:**
The mental model from React 18 (before RSC) was "client components are the default." Developers add `"use client"` broadly for safety and don't realize the subtree impact.

**How to avoid:**
Apply the "push interactivity to the leaves" rule: extract interactive elements (filters, buttons, toggles) into their own small client components. Keep data-display components (cards, charts, tables) as server components where possible.

```
DashboardPage (server) → SummaryCards (server) → SummaryCard (server)
                       → DateRangeFilter (client) ← interactive leaf only
                       → RecentTransactions (server)
```

For chart components: they must be `"use client"` because of TanStack Charts, but they should receive pre-shaped data as props from a server parent, not do their own fetching.

**Warning signs:**
- Lighthouse shows JS bundle over 500KB for a mostly-static dashboard
- React DevTools profiler shows no server components in the tree (everything is orange/client)
- Adding one interactive element to a page breaks Suspense streaming for unrelated sections

**Phase to address:** Dashboard page (Phase 1) — the architecture decision must be made early. Retrofitting RSC boundaries later requires rewriting component hierarchies.

---

### Pitfall 10: Clerk Middleware + Next.js — CVE-2025-29927 Middleware Bypass

**What goes wrong:**
Next.js versions prior to 15.2.3 (and 14.2.25 for v14) have a critical vulnerability (CVE-2025-29927, CVSS 9.1) where middleware-based authentication can be bypassed on self-hosted deployments by manipulating the `x-middleware-subrequest` header. If the app relies solely on Clerk middleware to protect routes, attackers can access protected pages without authentication.

**Why it happens:**
The vulnerability is in Next.js itself, not Clerk. Self-hosted deployments are at greater risk than Vercel deployments (which have additional edge protections). Applications that treat middleware as the *only* auth layer (no server-side validation in route handlers or server components) are fully exposed.

**How to avoid:**
- Verify Next.js is pinned to `>=15.2.3` in `package.json`
- Do not rely solely on middleware for authorization — also validate auth tokens in Server Components and Route Handlers at the data access layer using `auth()` from `@clerk/nextjs/server`
- Apply the Data Access Layer pattern: check `auth()` at every data access point, not just at the middleware boundary

**Warning signs:**
- Next.js version below 15.2.3 in `package.json`
- Route protection exists only in `middleware.ts`, with no server-side `auth()` calls in page or API files
- Protected pages accessible when `x-middleware-subrequest` header is present

**Phase to address:** Project setup (before any authenticated pages are built). Verify the Next.js version constraint immediately.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Inline chart data construction (no `useMemo`) | Faster to write | Infinite re-render loops; CPU-bound charts | Never — always memoize chart options |
| `"use client"` on container components | Avoids thinking about RSC boundaries | Bloated bundle; breaks streaming; harder to split later | Only for truly interactive leaf components |
| Single monolithic page component (all logic in one file) | Fast initial development | Existing Sidebar is already 741 lines — don't repeat; hard to test, hard to split | MVP only if file stays under 200 lines |
| Hard-coding currency as `EUR` | Simpler rendering | Won't format correctly if user changes locale | Acceptable for this milestone; use `Intl.NumberFormat` with locale param from the start |
| No skeleton screens for initial data load | Simpler component structure | Jarring content shift on slow connections; CONCERNS.md confirms no caching on backend | Never — skeleton screens are required per PROJECT.md |
| Fetching all transactions then filtering client-side | Simpler filtering logic | Memory pressure with large datasets; backend supports server-side filters | Only for <500 transactions; use server-side pagination at 25/page per PROJECT.md |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| TanStack Charts + Next.js | Direct import from `react-charts` in any file | Always `dynamic(() => import('react-charts').then(m => m.Chart), { ssr: false })` |
| React Query + App Router | `new QueryClient()` at module scope | `useState(() => new QueryClient())` in client provider |
| Clerk + Server Components | Calling `auth()` only in middleware | Call `auth()` inside every Server Component and Route Handler that returns user data |
| shadcn/ui + Tailwind 4 | Using `hsl(var(--color))` syntax in component styles | Use `var(--color)` directly — Tailwind 4 wraps values in OKLCH automatically |
| React Query + AI mutations | Not disabling button during `isPending` | Gate button on both `mutation.isPending` and backend-returned cooldown timestamp |
| Suspense + data fetching | `<Suspense>` inside the component that fetches | Place `<Suspense>` in parent, wrapping the fetching child as `fallback` sibling |
| shadcn/ui Table + mobile | Relying on `ScrollArea` for horizontal overflow | Use `div` with `overflow-x-auto` for horizontal; `ScrollArea` only for vertical |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Unmemoized chart options | Infinite re-render loop, frozen tab | `useMemo` on all `data`, `primaryAxis`, `secondaryAxes` | Immediately on first render |
| Double-fetch after SSR hydration | Duplicate API calls in Network tab | Set `staleTime: 60000` in QueryClient defaults | Every page load with SSR prefetch |
| Fetching all transactions for client-side filters | Page slow to load, high memory on 1000+ rows | Server-side filter params, paginate at 25/page | ~500+ transactions |
| Insight generation not rate-limited on frontend | Concurrent LLM requests, slow response for everyone | Disable button during `isPending`, enforce backend cooldown | 2+ rapid clicks |
| No analytics request caching | Analytics re-runs full calculation every tab switch | `staleTime: 5 * 60 * 1000` on analytics queries; rely on backend response | Every page focus event |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Next.js < 15.2.3 with middleware-only auth | Full auth bypass via CVE-2025-29927 | Pin `next >= 15.2.3`; add server-side `auth()` calls |
| Displaying raw transaction descriptions without sanitization | XSS if bank export contains script content | Use React's default escaping; never use `dangerouslySetInnerHTML` for transaction data |
| Exposing user ID in client-side React Query keys | User can read other users' keys from DevTools | Acceptable for this private app; for public: include only non-guessable identifiers |
| No CSRF protection on CSV upload mutation | CSRF attack triggering uploads from attacker site | Clerk JWTs sent as `Authorization` header (not cookie) are inherently CSRF-resistant |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| No skeleton screens during data load | Content flash / jarring layout shift | Skeleton for every card, table, and chart — required by PROJECT.md |
| "Generate Insights" with no cooldown UI | User clicks multiple times, unsure if it worked | Disable button + show countdown timer from backend `next_available_at` response field |
| Full-page loading spinner | User cannot read other content while waiting | Suspense per-section; sidebar and header always visible while content streams in |
| Empty state shows nothing | Users with no transactions see a blank page | Show a "Upload your first CSV" CTA with illustrated empty state on all pages |
| EUR currency hardcoded without `Intl.NumberFormat` | Incorrect formatting for `1234.56` vs `1.234,56` (German locale) | Use `Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' })` from day one |
| Mobile table with 6 columns | Columns squashed unreadably below 400px | Collapse to card layout at `sm:` breakpoint; show only date, description, amount on mobile |

---

## "Looks Done But Isn't" Checklist

- [ ] **Charts:** Chart renders in dev but crashes in production `next build` — test `npm run build` locally before any PR
- [ ] **Charts:** Chart appears but re-renders infinitely on slower machines — check React DevTools profiler for mount loops
- [ ] **React Query:** Data loads on page but re-fetches on every tab focus — verify `staleTime` is non-zero in QueryClient
- [ ] **Mobile:** Table looks fine on desktop — test at 375px (iPhone SE) specifically on the transactions page
- [ ] **Empty states:** Page works with data — verify all pages render correctly with zero transactions (test with a new user account)
- [ ] **Insights button:** Clicking once works — test double-click and rapid multi-click to confirm button is locked during `isPending`
- [ ] **Dark mode:** Components look correct in light mode — verify all custom teal/cream/charcoal tokens resolve in dark mode
- [ ] **Skeleton screens:** Each card has a skeleton — every data section must have a matching `*Skeleton` component before it is considered done
- [ ] **Error boundaries:** Happy path works — trigger a 500 from the API and verify graceful error fallback, not a blank page
- [ ] **Auth on page load:** Dashboard loads — verify behavior when Clerk session token is expired mid-session (should redirect to login, not crash)

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Charts crashing due to missing `ssr: false` | LOW | Add `dynamic()` wrapper to the chart component; no other code changes needed |
| Infinite re-render loop from unmemoized options | LOW | Add `useMemo` wrappers to chart options; identify the unstable reference with React DevTools profiler |
| QueryClient shared across requests (data leak) | MEDIUM | Refactor provider to use `useState`; clear all affected caches; test with concurrent users |
| `"use client"` pushed too high (bundle bloat) | HIGH | Requires decomposing components into server/client split; test streaming before and after |
| Tailwind 4 / shadcn color breakage | MEDIUM | Audit `globals.css` for `hsl()` wrappers; run shadcn upgrade codemod; re-test all color tokens |
| Next.js CVE middleware bypass | CRITICAL | Upgrade Next.js immediately; add `auth()` to all server data access points; test auth bypass scenario |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| TanStack Charts SSR crash | Phase 1 (Dashboard — first chart) | Run `npm run build` and verify no module-not-found errors for d3 |
| Charts infinite re-render | Phase 1 (Dashboard) + Phase 3 (Analytics) | React DevTools profiler shows chart component mounts once per navigation |
| QueryClient scope | Project setup (before Phase 1) | Open DevTools: no duplicate API calls on page load after SSR |
| Double-fetch after SSR | Project setup / Provider config | Network tab: no repeat calls within 60 seconds of initial load |
| Tailwind 4 color mismatch | Phase 1 (Design system) | All `--chart-*` and brand color tokens resolve in both light and dark mode |
| Suspense boundary misplacement | Phase 1 (Dashboard skeleton screens) | Throttle network to "Slow 3G": skeleton screens appear before content |
| AI button no cooldown | Phase 4 (Insights page) | Rapid-click test: button remains disabled; only one request fires |
| Mobile table overflow | Phase 2 (Transactions page) | Viewport 375px: table scrolls horizontally without full-page horizontal scroll |
| "use client" too high | Phase 1 (architecture) | React DevTools: page has server components; Lighthouse JS bundle < 300KB |
| Clerk CVE / middleware-only auth | Project setup | `package.json` shows `next >= 15.2.3`; each data route has `auth()` call |

---

## Sources

- [TanStack React Charts SSR Issue #324 — d3 ESM incompatibility and `ssr: false` workaround](https://github.com/TanStack/react-charts/issues/324) — HIGH confidence (official GitHub issue)
- [TanStack React Charts API Reference — memoization requirements](https://react-charts.tanstack.com/docs/api) — HIGH confidence (official docs)
- [shadcn/ui Tailwind v4 migration guide](https://ui.shadcn.com/docs/tailwind-v4) — HIGH confidence (official docs)
- [shadcn/ui issue #6427 — Tailwind v4 upgrade](https://github.com/shadcn-ui/ui/issues/6427) — HIGH confidence (official repo)
- [TanStack Query Advanced SSR guide](https://tanstack.com/query/latest/docs/framework/react/guides/advanced-ssr) — HIGH confidence (official docs)
- [Vercel — Common mistakes with the Next.js App Router](https://vercel.com/blog/common-mistakes-with-the-next-js-app-router-and-how-to-fix-them) — HIGH confidence (Vercel engineering blog)
- [TanStack Query discussion #5725 — App Router compatibility](https://github.com/TanStack/query/discussions/5725) — HIGH confidence (official repo)
- [shadcn/ui issue #416 — Table horizontal scroll whitespace bug](https://github.com/shadcn-ui/ui/issues/416) — MEDIUM confidence (community issue)
- [Next.js CVE-2025-29927 — middleware auth bypass](https://clerk.com/articles/complete-authentication-guide-for-nextjs-app-router) — HIGH confidence (Clerk engineering + CVE record)
- [Borstch — Building financial dashboards with TanStack React Charts](https://borstch.com/blog/development/building-a-financial-dashboard-in-react-with-tanstack-react-charts-library) — MEDIUM confidence (community article, verified against official docs)

---

*Pitfalls research for: Next.js 16 App Router personal finance dashboard*
*Researched: 2026-02-26*
