# Project Research Summary

**Project:** Personal Finance App — Web Dashboard (Frontend Milestone)
**Domain:** Personal finance dashboard with AI-powered insights, CSV import, and analytics
**Researched:** 2026-02-26
**Confidence:** HIGH

## Executive Summary

This is an additive frontend milestone layered on top of a finalized FastAPI backend. The architecture is a Next.js 16 App Router application with a client-first data fetching model: Server Components handle layout and routing shells, while all data fetching happens in Client Components via React Query hooks that call the backend with Clerk JWT tokens. The stack is almost entirely predetermined by what is already installed — the only new dependency confirmed after research is shadcn Chart (Recharts) via `npx shadcn add chart`, which was selected as the single chart library for all chart types (pie, line, bar, area).

The user decided during research review to consolidate all charting onto shadcn Chart (Recharts) rather than mixing react-charts with shadcn's chart component. This is the cleaner choice: Recharts supports every required chart type (pie, line, bar, area), integrates natively with the shadcn design system and OKLCH color tokens already defined in `globals.css`, is actively maintained, and avoids the SSR/dynamic-import complexity that comes with react-charts (which depends on D3 ESM-only packages). All chart components still require `"use client"` and should use `next/dynamic` with `ssr: false` to prevent hydration issues.

The primary risks in this build are architectural rather than feature-level: charts breaking in production due to missing `dynamic()` wrappers, infinite re-render loops from unmemoized chart options, mobile table overflow without explicit scroll containers, and the Clerk CVE-2025-29927 middleware bypass if Next.js is below 15.2.3. All of these have clear, well-documented prevention patterns. Feature scope is well-defined with a full backend API already in place — no API design work is needed.

## Key Findings

### Recommended Stack

The stack is locked in at every layer. The only install action required before building is running `npx shadcn add chart` in the `web-app` directory to pull in the Recharts-backed chart component and generate `src/components/ui/chart.tsx`. All other libraries (React Query, Clerk, TanStack Table, sonner, next-themes, Tailwind v4, shadcn/ui) are already installed and configured.

The existing codebase follows a 3-layer API pattern (pure fetch function → React Query hook → component) that must be followed for all new data-fetching features. React Query's QueryProvider is already configured with sensible defaults (`staleTime: 60s`, `gcTime: 5min`, `refetchOnWindowFocus: false`). No global state manager (Zustand, Jotai, Context) is needed — React Query handles all server state, local `useState` handles all UI state.

**Core technologies:**
- **Next.js 16 + React 19:** Framework — App Router with Server Components for layout, Client Components for all data fetching
- **shadcn/ui Chart (Recharts):** All charts — pie, line, bar, area; integrates natively with OKLCH design tokens; install via `npx shadcn add chart`
- **@tanstack/react-query v5:** Server state — all API calls go through hooks; `placeholderData: keepPreviousData` for paginated tables
- **@tanstack/react-table v8:** Transaction table — sort, filter, pagination; already installed
- **@clerk/nextjs v6:** Auth — `useAuth().getToken()` in every API hook; middleware protects all routes
- **Tailwind CSS v4 + shadcn/ui v3:** Styling — CSS-first config, OKLCH colors, `tw-animate-css` (not `tailwindcss-animate`)
- **sonner v2:** Toast notifications — already configured in root layout

### Expected Features

**Must have (table stakes) — all P1 for this milestone:**
- Dashboard: 4 summary KPI cards (income, expenses, net, savings rate with MoM delta), category pie chart, monthly trend line chart, recent transactions widget (last 5-10), AI insights callout card
- Transactions: paginated table (25/page, offset-based), search by merchant, date range filter with presets, category multi-select filter, single-transaction category edit modal, bulk category reassign, bulk delete
- Analytics: 4-tab page (spending by category bar chart, income vs expenses line/bar chart, month-over-month trends, seasonality/behavior heatmap)
- Insights: insight card grid (spending / recurring / savings / anomalies / comparisons), savings tracker, regenerate button with 60-second client-side cooldown
- Budgets: "Coming Soon" placeholder page
- Cross-cutting: skeleton screens on every data-fetching section, contextual empty states with CTAs, toast notifications for mutations, EUR formatting via `Intl.NumberFormat('de-DE')`, dark mode via Tailwind `dark:` classes, responsive sidebar collapsing to hamburger at `<768px`

**Should have (differentiators) — P2, add post-launch:**
- Confidence score badges on transaction rows (amber for <0.85 confidence)
- Anomaly callout cards from `/analytics/anomalies`
- Recurring expenses tracker from `/analytics/recurring`
- URL-persisted filter state via `useSearchParams`
- Merchant concentration risk callout

**Defer to v2+:**
- Budget creation (no backend API)
- CSV export (no backend endpoint)
- Bank connection via open banking API (compliance, cost, backend work)
- Natural language chatbot UI (out of scope per PROJECT.md)

### Architecture Approach

The frontend uses a **client-first architecture with server layout shells**: every `page.tsx` is a thin Server Component that renders a single Client Component root (e.g., `<DashboardPage />`). All data fetching, interactivity, and chart rendering lives in Client Components. Components are organized by page (`components/dashboard/`, `components/transactions/`, etc.) with a `components/shared/` directory for reusable primitives (charts, skeletons, transaction table, empty state). Types live in `types/` matching Pydantic schemas; API functions in `lib/api/`; React Query hooks in `hooks/`.

**Major components:**
1. `lib/api/client.ts` — shared authenticated fetch utility (base for all API functions)
2. `hooks/use-*.ts` — React Query wrappers (use-transactions, use-analytics, use-insights, use-dashboard)
3. `components/shared/charts/` — Recharts wrappers via shadcn Chart, all `"use client"` with `next/dynamic` ssr:false
4. `components/shared/transaction-table/` — TanStack Table-backed, mode prop for compact vs full
5. Page root components (`dashboard-page.tsx`, `transactions-page.tsx`, etc.) — Client Component boundaries
6. `types/` (transaction.ts, analytics.ts, insights.ts) — TypeScript types matching backend schemas

### Critical Pitfalls

1. **Charts crashing in production due to missing `ssr: false`** — Recharts (and any charting library using browser APIs) must be wrapped with `next/dynamic(..., { ssr: false })`. Build succeeds in dev but fails in `next build`. Establish this pattern on the first chart component; all subsequent chart components copy it.

2. **Chart infinite re-render loop from unmemoized options** — All chart data transforms and axis definitions must be wrapped in `useMemo`. Raw API responses passed directly as chart props cause React to detect "new" object references on every render, triggering a mount loop that freezes the tab. This is non-optional.

3. **QueryClient created at module scope — user data leaks** — The QueryClient must be instantiated inside `useState` in the provider component, not at module scope. Module-scope singletons are shared across server-rendered requests. The existing `QueryProvider` already does this correctly; do not introduce new QueryClient instances elsewhere.

4. **Clerk CVE-2025-29927 — middleware-only auth bypass** — Verify Next.js is `>=15.2.3` in `package.json`. Do not rely solely on middleware for route protection; call `auth()` from `@clerk/nextjs/server` in every Server Component and Route Handler that returns user data.

5. **Mobile table overflow without scroll container** — shadcn `Table` does not scroll horizontally by default. Wrap in `<div className="w-full overflow-x-auto">`, not `ScrollArea` (which introduces a whitespace bug on horizontal+vertical scroll). Test at 375px viewport (iPhone SE) before marking transactions page complete.

6. **Tailwind v4 color syntax: `hsl()` wrappers break color resolution** — In Tailwind v4, theme variables are OKLCH values; do not wrap them in `hsl()`. Use `var(--chart-1)` not `hsl(var(--chart-1))`. The project's `globals.css` is already correct — avoid copying from older shadcn tutorials that use the v3 pattern.

7. **AI Insights: no cooldown causes concurrent LLM requests** — The insights endpoint generates synchronously on first call (can take 15-60 seconds). Without button locking, rapid clicks fire multiple concurrent generation requests. Gate the button on both `mutation.isPending` and a client-side 60-second cooldown timer.

## Implications for Roadmap

Based on research, 7 phases are suggested matching the ARCHITECTURE.md build order. Each phase's output is a clear dependency for the next.

### Phase 1: Foundation — API Layer, Types, and Hooks
**Rationale:** Everything else depends on this. No UI component can be built without knowing the data shape and having working hooks. Building and validating this layer in isolation (console.log tests) prevents debugging data issues inside complex UI later.
**Delivers:** `lib/api/client.ts`, `lib/api/transactions.ts`, `lib/api/analytics.ts`, `lib/api/insights.ts`; all TypeScript types; all React Query hooks (use-transactions, use-analytics, use-insights, use-dashboard)
**Addresses:** Transactions table, analytics tabs, insights page, dashboard — all depend on these hooks
**Avoids:** Data leaking between components, prop-drilling auth tokens (token stays inside hooks), double-fetch after hydration (staleTime configured once here)
**Research flag:** SKIP — well-documented pattern already established in codebase. Copy the `use-server-status.ts` + `lib/api/health.ts` pattern.

### Phase 2: Shared Display Components
**Rationale:** These are pure prop-driven display components with no data fetching dependency. Build them with mock data, validate visually, then wire to real hooks in later phases. Chart wrappers built here establish the `dynamic/ssr:false` and `useMemo` patterns that all chart usage must follow.
**Delivers:** `components/shared/skeleton/` (card, table, chart skeletons), `components/shared/empty-state.tsx`, `components/shared/charts/` (pie, line, bar, area — all Recharts via shadcn Chart), `components/shared/transaction-table/` (with compact/full mode prop)
**Uses:** shadcn Chart (Recharts) via `npx shadcn add chart`; shadcn Skeleton, Table; @tanstack/react-table
**Avoids:** Chart SSR crash (dynamic/ssr:false established here); chart re-render loops (useMemo pattern established here); mobile table overflow (overflow-x-auto wrapper established here)
**Research flag:** SKIP for skeletons and empty states (standard patterns). VERIFY chart wrapper pattern compiles cleanly with `npm run build` before moving on.

### Phase 3: Dashboard Page
**Rationale:** First page users see; must demonstrate value immediately. Uses all shared components built in Phase 2, validating the full data → hook → component flow end-to-end. The pie chart (spending by category) and line chart (monthly trend) are the primary chart test cases.
**Delivers:** `components/dashboard/summary-cards.tsx`, `components/dashboard/recent-transactions.tsx`, `components/dashboard/insights-callout.tsx`, `components/dashboard/dashboard-page.tsx`; updated `app/(app)/home/page.tsx`
**Addresses:** 4 summary KPI cards, category pie chart, monthly trend chart, recent transactions widget, AI insights callout — all P1 table stakes
**Avoids:** `"use client"` pushed too high (DashboardPage is the Client boundary; page.tsx stays Server); Suspense misplacement (Suspense wraps fetching children from page.tsx)
**Research flag:** SKIP — patterns well-established. Run `npm run build` to verify chart SSR is handled correctly.

### Phase 4: Transactions Page
**Rationale:** Heaviest interaction page with the most state (filters, pagination, selection, modals, mutations). Build after Dashboard so the API hook and shared table component patterns are proven. Bulk actions require the checkbox column — build them together, not sequentially.
**Delivers:** `components/transactions/category-edit-modal.tsx`, `components/transactions/bulk-action-bar.tsx`, `components/transactions/transactions-page.tsx`; updated `app/(app)/transactions/page.tsx`
**Addresses:** Paginated table, search/filter (date, category), category edit modal, bulk reassign, bulk delete — all P1
**Avoids:** Client-side filtering of all transactions (use server-side filter params + 25/page pagination); mobile table overflow (overflow-x-auto from Phase 2); optimistic UI rollback on category edit mutation failure
**Research flag:** SKIP for table/filter patterns. VERIFY bulk mutation endpoints (PATCH and DELETE `/transactions/batch`) match the backend schema before building the bulk action bar.

### Phase 5: Analytics Page
**Rationale:** Depends on chart wrappers (Phase 2) and analytics hooks (Phase 1). Four tabs are independent and can be built in parallel but should ship together as one tabbed page to avoid a partial-feeling UX. Lazy-load each tab with `enabled: activeTab === "..."` to avoid firing 4+ analytics API calls on mount.
**Delivers:** All 4 tab components (spending-by-category, income-expenses, trends, seasonality); `analytics-tabs.tsx`; `analytics-page.tsx`; `app/(app)/analytics/page.tsx`
**Addresses:** All 4 analytics tabs — P1 per FEATURES.md ("this is the depth that justifies the app")
**Avoids:** Fetching all tabs on mount (use `enabled` flag per tab); analytics re-runs on every tab switch (staleTime: 5min on analytics queries)
**Research flag:** SKIP — tab pattern + lazy enabled flag is standard React Query. Chart types (bar, line) are covered by Phase 2 wrappers.

### Phase 6: Insights Page
**Rationale:** The AI value proposition page. The insights endpoint generates synchronously on first call (can take 15-60 seconds); the loading UX must communicate this clearly. The regenerate button requires careful cooldown implementation to avoid concurrent LLM requests.
**Delivers:** `components/insights/insight-card.tsx`, `components/insights/insights-grid.tsx`, `components/insights/generate-button.tsx`, `components/insights/insights-page.tsx`; `app/(app)/insights/page.tsx`
**Addresses:** Insight cards grid, savings tracker, regenerate button with cooldown — all P1
**Avoids:** No cooldown causing concurrent LLM requests (button disabled during isPending + 60s client-side timer); polling (backend generates synchronously; use a single query with long gcTime: 30min); state update on unmounted component (gcTime keeps query alive during navigation)
**Research flag:** NEEDS ATTENTION — verify the regenerate button flow matches the actual backend behavior (GET-only vs POST trigger). Confirm whether `/insights` generates on GET or requires a separate trigger endpoint.

### Phase 7: Responsive Polish, Budgets Placeholder, and Final QA
**Rationale:** Mobile responsiveness and cross-cutting quality checks are deferred to a dedicated phase rather than scattered across phase development, where they would slow down feature velocity. The "Looks Done But Isn't" checklist from PITFALLS.md must be completed here.
**Delivers:** Budgets "Coming Soon" placeholder page; sidebar hamburger collapse on mobile; 48px tap targets throughout; chart card layout at `<sm` breakpoint for transaction table; verified dark mode for all custom color tokens; final `npm run build` clean run
**Addresses:** Responsive layout, dark mode, Budgets placeholder — all P1 per FEATURES.md
**Research flag:** SKIP — standard Tailwind responsive patterns. Test specifically at 375px (iPhone SE) for table and chart legibility.

### Phase Ordering Rationale

- **Hooks before UI:** Every page component depends on API hooks returning typed data. Building hooks first means UI components never need to mock or stub data — they wire to real endpoints from day one.
- **Shared components before pages:** The chart wrappers, skeleton components, and transaction table appear on multiple pages. Building them once with mock data, validating the SSR/memoization patterns, then wiring real data prevents the same patterns from being implemented inconsistently across pages.
- **Dashboard before Transactions:** Dashboard validates the full end-to-end flow (hook → data → chart) with less interaction complexity than Transactions. Errors found here are easier to isolate.
- **Insights last among data pages:** The synchronous LLM generation makes this the most latency-sensitive page. Leaving it last means the loading/error patterns are mature from prior phases.
- **Polish as a dedicated phase:** Mobile layout and dark mode touch every component. A final dedicated phase catches regressions introduced during feature development rather than forcing per-component mobile testing throughout.

### Research Flags

Phases needing verification or deeper attention during planning:
- **Phase 6 (Insights):** Confirm whether the backend `/insights` endpoint generates on GET or requires a separate POST/trigger call. The architecture notes say "generates synchronously on first GET" but this should be verified against the actual backend route handler before designing the regenerate button flow.
- **Phase 4 (Transactions — batch endpoints):** Confirm the exact request shape for `PATCH /transactions/batch` and `DELETE /transactions/batch` (array of IDs? body vs query params?) before implementing the bulk action bar.

Phases with well-established patterns (research-phase not needed):
- **Phase 1:** The `lib/api/health.ts` + `use-server-status.ts` pattern is the template. Follow it exactly.
- **Phase 2:** shadcn Skeleton and empty state are well-documented. Chart wrappers follow Recharts + shadcn Chart official examples.
- **Phase 3:** Dashboard layout is a standard shadcn card grid pattern.
- **Phase 5:** Tab-based lazy loading with React Query `enabled` flag is a well-documented pattern.
- **Phase 7:** Tailwind responsive classes and dark mode are standard.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Most of the stack is already installed; only `npx shadcn add chart` is new. User confirmed Recharts (via shadcn Chart) as the single chart library. No version conflicts expected. |
| Features | HIGH | Backend API is finalized and fully enumerated. Feature list is derived directly from backend endpoint surface, not speculative. Anti-features explicitly documented to prevent scope creep. |
| Architecture | HIGH | Based on direct codebase inspection. The existing `use-server-status.ts` / `lib/api/health.ts` pattern is confirmed working. Server/Client component split follows official Next.js App Router guidance. |
| Pitfalls | HIGH | All critical pitfalls verified against official docs, GitHub issues, or Vercel engineering blog. The CVE (Pitfall 10) is a known public vulnerability with a clear fix. |

**Overall confidence:** HIGH

### Gaps to Address

- **Regenerate insights trigger mechanism:** Architecture research notes that the insights endpoint generates synchronously on the first GET. If a future backend change introduces a separate POST trigger for regeneration, the generate-button component will need to change from `queryClient.invalidateQueries()` to a `useMutation` POST. Verify this before Phase 6 implementation.
- **Batch endpoint request schemas:** The backend PATCH and DELETE `/transactions/batch` endpoints need their request body shapes confirmed (IDs as array in body vs query params) before the bulk action bar is implemented. This is a quick check against the FastAPI route handlers, not a research task.
- **react-error-boundary package:** PITFALLS.md recommends wrapping each page in an error boundary. shadcn does not provide one. Confirm whether the `react-error-boundary` npm package is acceptable to add, or whether a custom implementation is preferred, before Phase 3.

## Sources

### Primary (HIGH confidence)
- Existing codebase: `web-app/src/` — stack confirmed from `package.json`, `globals.css`, `components.json`, `query-provider.tsx`
- [shadcn/ui Tailwind v4 docs](https://ui.shadcn.com/docs/tailwind-v4) — OKLCH colors, tw-animate-css, v4 migration patterns
- [shadcn/ui pie chart examples](https://ui.shadcn.com/charts/pie) — Recharts-backed pie component
- [Next.js App Router Server/Client docs](https://nextjs.org/docs/app/getting-started/server-and-client-components) — server/client boundary rules
- [TanStack Query Advanced SSR guide](https://tanstack.com/query/latest/docs/framework/react/guides/advanced-ssr) — QueryClient scoping, staleTime defaults
- [Vercel — Common App Router mistakes](https://vercel.com/blog/common-mistakes-with-the-next-js-app-router-and-how-to-fix-them) — Suspense placement, "use client" scoping
- [Next.js CVE-2025-29927](https://clerk.com/articles/complete-authentication-guide-for-nextjs-app-router) — middleware auth bypass, requires Next.js >=15.2.3

### Secondary (MEDIUM confidence)
- [TanStack react-charts GitHub issue #324](https://github.com/TanStack/react-charts/issues/324) — Next.js dynamic import `ssr: false` pattern (relevant as rationale for why Recharts was chosen over react-charts)
- [shadcn/ui issue #416](https://github.com/shadcn-ui/ui/issues/416) — Table horizontal scroll whitespace bug with ScrollArea
- [Fintech UX Best Practices 2026 — Eleken](https://www.eleken.co/blog-posts/fintech-ux-best-practices) — feature prioritization and mobile finance UX
- [Data Table Design Patterns — Pencil & Paper](https://www.pencilandpaper.io/articles/ux-pattern-analysis-enterprise-data-tables) — pagination over infinite scroll for finance data
- [Skeleton Screens 101 — Nielsen Norman Group](https://www.nngroup.com/articles/skeleton-screens/) — skeleton screen implementation rationale

### Tertiary (LOW confidence — inferred from multiple sources)
- Insights endpoint synchronous generation behavior: inferred from API description + FastAPI route inspection; confirm against live backend before building Insights page

---
*Research completed: 2026-02-26*
*Ready for roadmap: yes*
