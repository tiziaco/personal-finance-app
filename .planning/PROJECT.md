# Personal Finance Dashboard

## What This Is

A personal finance tracking web application for a small group of users (friends and family). Users upload CSV bank exports, view AI-categorized transaction breakdowns, analyze spending patterns across four dimensions, and receive AI-generated savings insights. Built as a Next.js 16 frontend (`/web-app`) consuming a finalized FastAPI backend (`/server`). All seven planned pages are fully implemented and polished for mobile and dark mode.

## Core Value

Users can understand where their money goes — at a glance on the dashboard, and in depth through analytics and AI insights — without any manual data entry beyond uploading a CSV.

## Requirements

### Validated

- ✓ User authentication via Clerk (JWT, middleware-based) — existing
- ✓ Navigation shell with sidebar (home, transactions, stats pages) — existing
- ✓ Settings modal with account section and logout — existing
- ✓ Backend API fully implemented (transactions, analytics, insights, auth endpoints) — existing
- ✓ Backend connection established and tested — existing
- ✓ React Query provider configured — existing
- ✓ shadcn/ui component library installed — existing
- ✓ CSV upload and transaction labeling pipeline — existing (backend)
- ✓ Dashboard page: welcome card, 4 summary cards, pie + line charts, recent transactions, AI insights callout — v1.0
- ✓ Transactions page: filterable/searchable table, bulk recategorize, pagination, category edit modal — v1.0
- ✓ Analytics page: 4-tab lazy-loaded page (spending by category, income vs expenses, MoM trends, seasonality) — v1.0
- ✓ Insights page: generate button with cooldown, insight cards in 5 category tabs, savings tracker — v1.0
- ✓ Budgets page: placeholder with "Coming Soon" message — v1.0
- ✓ Settings: currency preference (EUR/USD/GBP/CHF), date format, dark mode toggle, delete all transactions — v1.0
- ✓ Responsive layout: collapsible sidebar with mobile hamburger, 48px tap targets, mobile card-list — v1.0
- ✓ Design system: semantic OKLCH tokens (teal primary, warm gray secondary, cream/charcoal bg) — v1.0
- ✓ Loading states: skeleton screens throughout, spinners for async actions — v1.0
- ✓ Toast notifications for all user-initiated actions — v1.0
- ✓ Error boundaries and graceful empty states on all pages — v1.0

### Active

*(None — all v1.0 scope delivered. See v2 requirements below.)*

### Out of Scope

- Modifying the `/server` backend — backend is finalized, frontend consumes it as-is
- Real-time chat/chatbot UI — backend has agent, not in this milestone's UI scope
- Budget creation API — budgets page is placeholder only, no API available
- Mobile native app — web-first
- Download all data endpoint — no backend endpoint available
- OAuth login (Google/GitHub) — Clerk handles auth, not in scope
- Bulk CSV export — no backend endpoint in v1
- Infinite scroll on transactions — pagination is the correct UX
- Inline row editing — modal is correct UX for finance data

## Context

- **Shipped:** v1.0 (2026-03-03), 7 phases, 29 plans, 11 days
- **Codebase:** ~8,255 LOC TypeScript/TSX, 262 files changed
- **Tech stack:** Next.js 16, React 19, TypeScript 5, Tailwind CSS 4 (OKLCH), shadcn/ui, Recharts (via shadcn Chart), TanStack Table v8, TanStack Query v5, Clerk, sonner
- **Charts:** Switched from TanStack React Charts (user-specified pre-roadmap) to shadcn Chart (Recharts) — avoids SSR/dynamic-import complexity; integrates natively with OKLCH tokens
- **Key patterns:** amount as string (Decimal precision), shadow-import hooks for currency/date format, visitedTabs lazy-load for analytics, stale-time ladder (transactions=30s → insights=10min)
- **Known issues:** None blocking. FOUND-03 checkbox in REQUIREMENTS.md not ticked (documentation artifact — hooks were fully implemented in Phase 1 Plan 05)

## Constraints

- **Tech Stack:** Next.js 16 + React 19 + TypeScript 5 + Tailwind CSS 4 — no framework changes
- **Charts:** shadcn Chart (Recharts) — switched from TanStack React Charts due to SSR issues
- **Backend:** Read-only — no server modifications; use existing API contracts from `/server/app/api/`
- **Existing functionality:** Do not alter settings modal, auth flow, or any currently working feature
- **Currency default:** EUR (user is based in Berlin)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| shadcn Chart (Recharts) instead of TanStack React Charts | SSR/dynamic-import complexity; OKLCH token integration | ✓ Good |
| shadcn/ui for non-chart UI | Already installed, consistent with existing codebase | ✓ Good |
| Budgets page as placeholder | No backend budget API available yet | — Pending (v2) |
| Dashboard as Phase 2 priority (after Foundation) | First page users see; highest impact for quick wins | ✓ Good |
| Analytics tabs: category / income-expenses / MoM / seasonality | User confirmed these 4 dimensions as most important | ✓ Good |
| amount typed as string (not number) | Python Decimal serializes as JSON string; avoids float precision loss | ✓ Good |
| Clerk + React Query v5: getToken() inside queryFn | Token is not stable, should not be in queryKey | ✓ Good |
| stale-time ladder (30s → 10min by compute cost) | Proportional to backend compute cost | ✓ Good |
| visitedTabs Set for analytics lazy-load | Tab data only fetches once, on first visit | ✓ Good |
| Shadow-import hook pattern for currency/date format | Zero JSX changes at migration call sites | ✓ Good |
| TransactionCard (mobile) has no checkbox | Bulk actions are desktop-only for v1 | — Pending (v2) |
| SavingsTracker useState-only (no persistence) | v1 scope; localStorage/server persistence deferred | — Pending (v2) |

---
*Last updated: 2026-03-03 after v1.0 milestone*
