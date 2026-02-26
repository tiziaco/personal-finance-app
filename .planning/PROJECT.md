# Personal Finance Dashboard

## What This Is

A personal finance tracking and budgeting web application for a small group of users (friends and family). Users upload CSV bank exports, view AI-categorized transaction breakdowns, analyze spending patterns, and receive AI-generated savings insights. Built as a Next.js frontend (`/web-app`) consuming a finalized FastAPI backend (`/server`).

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

### Active

- [ ] Dashboard page: welcome card, 4 summary cards, pie + line charts, recent transactions widget, AI insights callout, CTAs
- [ ] Transactions page: filterable/searchable table, bulk actions, pagination (25/page), category edit modal
- [ ] Analytics page: tabbed layout with spending by category, income vs expenses, month-over-month trends, and seasonality analysis
- [ ] Insights page: generate button with cooldown, insight cards grid, insights by category (spending/recurring/savings/anomalies/comparisons), savings tracker
- [ ] Budgets page: placeholder with "Coming Soon" message
- [ ] Responsive layout: collapsible sidebar on mobile, hamburger menu, 48px tap targets
- [ ] Design system: teal (#208E95) primary, warm gray (#5E5240) secondary, cream (#FCFCF9) background, charcoal (#1F2121) dark mode
- [ ] Loading states: skeleton screens throughout, spinners for async actions
- [ ] Toast notifications for all user actions
- [ ] Error boundaries and graceful empty states on all pages

### Out of Scope

- Modifying the `/server` backend — backend is finalized, frontend consumes it as-is
- Real-time chat/chatbot UI — backend has agent, not in this milestone's UI scope
- Budget creation API — budgets page is placeholder only, no API available
- Mobile native app — web-first
- Download all data endpoint — placeholder UI only, no backend endpoint available
- OAuth login (Google/GitHub) — Clerk handles auth, not in scope

## Context

- **Monorepo structure:** `/server` (FastAPI, Python 3.13) and `/web-app` (Next.js 16, React 19, TypeScript 5)
- **Existing pages:** `(app)/home`, `(app)/stats`, `(app)/transactions` — navigate between these; do not break existing routing
- **Charts library:** TanStack React Charts (`react-charts.tanstack.com`) — already specified by user
- **UI library:** shadcn/ui for all components except charts
- **Design:** Use `/frontend-design` skill for all UI work; fintech aesthetic, minimal, professional
- **Analytics dimensions confirmed by user:** spending by category, income vs expenses, month-over-month trends, seasonality (spending by month/day-of-week)
- **User base:** Small group (friends + family), not public SaaS — auth already handles multi-user
- **Priority page:** Dashboard ships first

## Constraints

- **Tech Stack:** Next.js 16 + React 19 + TypeScript 5 + Tailwind CSS 4 — no framework changes
- **Charts:** TanStack React Charts only (user-specified)
- **Backend:** Read-only — no server modifications; use existing API contracts from `/server/app/api/`
- **Existing functionality:** Do not alter settings modal, auth flow, or any currently working feature
- **Design:** Use `/frontend-design` skill for all UI work; use context7 for documentation lookups
- **Currency default:** EUR (user is based in Berlin)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| TanStack React Charts for all charts | User-specified; avoids Recharts/Chart.js sprawl | — Pending |
| shadcn/ui for non-chart UI | Already installed, consistent with existing codebase | — Pending |
| Budgets page as placeholder | No backend budget API available yet | — Pending |
| Dashboard as Phase 1 priority | First page users see; highest impact for quick wins | — Pending |
| Analytics tabs: category / income-expenses / MoM / seasonality | User confirmed these 4 dimensions as most important | — Pending |

---
*Last updated: 2026-02-26 after initialization*
