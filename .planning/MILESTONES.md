# Milestones

## v1.0 MVP (Shipped: 2026-03-03)

**Phases completed:** 7 phases, 29 plans
**Files changed:** 262 files (40,667 insertions)
**LOC:** ~8,255 TypeScript/TSX
**Timeline:** 11 days (2026-02-21 → 2026-03-03)
**Git range:** Initial commit → feat(07-05): add currency-change toast

**Delivered:** Full web dashboard consuming a finalized FastAPI backend — dashboard, transactions, analytics, insights, budgets, and settings pages fully built and polished for mobile and dark mode.

**Key accomplishments:**
1. Typed API layer with React Query hooks for all backend endpoints (Clerk JWT auth, stale-time ladder)
2. Dashboard: welcome card, 4 color-coded summary cards, spending pie chart + 6-month trend chart, recent transactions, AI insights callout
3. Transactions: filterable/searchable TanStack Table v8, category edit modal, bulk recategorize, empty state with CSV CTA
4. Analytics: 4-tab lazy-loaded page (spending by category, income vs expenses, MoM trends, seasonality)
5. Insights: AI insight cards in 5 category tabs, savings tracker with checklist, generate button with 1-hour localStorage cooldown
6. Budgets + Settings: budgets placeholder, currency/date format preferences, dark mode toggle, delete-all-transactions with confirmation
7. Polish: semantic OKLCH design tokens, full dark mode, mobile hamburger sidebar, 48px tap targets, mobile card-list for transactions, universal toast + skeleton coverage

---

