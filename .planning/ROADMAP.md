# Roadmap: Personal Finance Dashboard

## Overview

Seven phases build the web dashboard from the inside out: first the typed API layer and shared UI primitives, then the highest-priority page (Dashboard), then the heaviest interaction surface (Transactions), then the data-depth pages (Analytics, Insights), and finally a polish phase that handles Budgets placeholder, Settings enhancements, full dark mode, and mobile responsiveness. Every phase delivers a coherent, independently verifiable capability before the next begins.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation** - API client, TypeScript types, React Query hooks, and shared display primitives (completed 2026-02-27)
- [ ] **Phase 2: Dashboard** - The first page users see; welcome card, summary cards, charts, recent transactions, insights callout
- [ ] **Phase 3: Transactions** - Filterable/searchable paginated table with category editing and bulk actions
- [ ] **Phase 4: Analytics** - Four-tab analytics page with lazy-loaded charts for each spending dimension
- [ ] **Phase 5: Insights** - AI insight cards, savings tracker, and regenerate button with cooldown
- [ ] **Phase 6: Budgets + Settings** - Budgets placeholder and Settings enhancements (currency, date format, theme, delete data)
- [ ] **Phase 7: Polish** - Dark mode, mobile responsiveness, design system tokens, and final QA

## Phase Details

### Phase 1: Foundation
**Goal**: The data layer and shared display components are fully typed, tested against the live backend, and ready to be consumed by any page without modification
**Depends on**: Nothing (first phase)
**Requirements**: FOUND-01, FOUND-02, FOUND-03, FOUND-04, FOUND-05, FOUND-06
**Success Criteria** (what must be TRUE):
  1. Every backend API response (transactions, analytics, insights, dashboard summary) has a corresponding TypeScript interface that exactly matches the Pydantic schema
  2. Every API endpoint can be called from the browser with a Clerk JWT token and returns typed data without a TypeScript error
  3. React Query hooks (useTransactions, useDashboardSummary, useAnalytics, useInsights, useCategories) exist and return loading/error/data states correctly when used in a component
  4. Pie, line, and bar chart wrapper components render with mock data in the browser without a hydration error or console error
  5. Skeleton and error boundary components exist and are visually correct when used in a page
**Plans**: TBD

### Phase 2: Dashboard
**Goal**: Users can understand their financial situation at a glance from the dashboard — current spending, category breakdown, trends, and the latest AI insight — within seconds of logging in
**Depends on**: Phase 1
**Requirements**: DASH-01, DASH-02, DASH-03, DASH-04, DASH-05, DASH-06, DASH-07, DASH-08
**Success Criteria** (what must be TRUE):
  1. User sees their name and total spending for the current month immediately on the home page
  2. User sees 4 summary cards (Total Spent, Remaining Budget, Recurring Costs, Savings Goal) with correct color coding — green for healthy, red for overspend
  3. User sees a spending-by-category pie chart (top 5 categories with interactive legend and percentages) and a 6-month trend line chart with hover tooltips
  4. User sees the last 5-10 transactions with date, merchant, amount, and category — and a "View All" link that navigates to the Transactions page
  5. User sees an AI insights callout with 1-2 highlights and can click "Upload CSV" or "View Insights" to navigate to those flows
**Plans**: 5 plans

Plans:
- [ ] 02-01-PLAN.md — Narrow DashboardResponse types + formatCurrency/formatDate utilities
- [ ] 02-02-PLAN.md — WelcomeCard and SummaryCards widgets (DASH-01, DASH-02)
- [ ] 02-03-PLAN.md — SpendingPieChart and TrendLineChart widgets (DASH-03, DASH-04)
- [ ] 02-04-PLAN.md — RecentTransactions and InsightsCallout widgets (DASH-05, DASH-06, DASH-07, DASH-08)
- [ ] 02-05-PLAN.md — Dashboard page composition + /upload route stub

### Phase 3: Transactions
**Goal**: Users can find, review, and recategorize any transaction in their history quickly, with bulk operations for handling many at once
**Depends on**: Phase 2
**Requirements**: TXN-01, TXN-02, TXN-03, TXN-04, TXN-05, TXN-06, TXN-07, TXN-08, TXN-09, TXN-10
**Success Criteria** (what must be TRUE):
  1. User can type in a search box and see matching transactions update in real time; user can apply date range, category, and amount range filters simultaneously
  2. User sees a paginated table of 25 transactions per page with Previous/Next controls and a "Showing X-Y of Z" count
  3. User can click a transaction's category or edit button to open a modal, select a new category, and save — the table reflects the change immediately
  4. User can select multiple transactions via checkboxes and apply a bulk recategorize action to all selected rows at once
  5. User sees an empty state with an illustration and "Upload a CSV" CTA when no transactions exist
**Plans**: TBD

### Phase 4: Analytics
**Goal**: Users can explore their spending across four dimensions (by category, income vs expenses, month-over-month trends, and seasonality) without waiting for all data to load at once
**Depends on**: Phase 3
**Requirements**: ANLT-01, ANLT-02, ANLT-03, ANLT-04, ANLT-05, ANLT-06
**Success Criteria** (what must be TRUE):
  1. User sees an Analytics page with four clearly labeled tabs and can switch between them without a full page reload
  2. Each tab loads its data only when first activated — switching tabs does not trigger re-fetches for already-visited tabs
  3. User can view spending by category with a date filter (1M / 3M / 6M) that updates the chart
  4. User can view income vs expenses as a bar chart by month and read a cash flow summary below it
  5. User can view month-over-month trends and seasonality patterns (by month and day of week) as charts
**Plans**: TBD

### Phase 5: Insights
**Goal**: Users can generate, browse, and act on AI-powered financial insights organized by type, with a savings tracker showing their total opportunity
**Depends on**: Phase 4
**Requirements**: INSGT-01, INSGT-02, INSGT-03, INSGT-04, INSGT-05, INSGT-06, INSGT-07
**Success Criteria** (what must be TRUE):
  1. User sees a "Generate New Insights" button and can click it to trigger AI generation — the button shows a loading state and disables during generation
  2. After generation, the button shows a countdown ("Refreshes in XX minutes") and remains disabled for 1 hour
  3. User sees insight cards organized into categories (Spending Patterns, Recurring Charges, Savings Opportunities, Anomalies, Comparisons) with title, icon, description, key metric, optional CTA, and timestamp
  4. User sees a savings tracker showing total potential monthly savings with a checklist to mark recommendations as done
  5. User sees an empty state with illustration and "Generate Insights" CTA when no insights exist yet
**Plans**: TBD

### Phase 6: Budgets + Settings
**Goal**: The Budgets page communicates future intent without misleading users, and Settings lets users control their currency, date format, theme, and data — all without breaking the existing settings modal
**Depends on**: Phase 5
**Requirements**: BUDG-01, SETT-01, SETT-02, SETT-03, SETT-04, SETT-05
**Success Criteria** (what must be TRUE):
  1. User sees a Budgets page with a prominent "Coming Soon" message and a brief description of what budgets will offer
  2. User can set currency preference (EUR default) and date format preference from Settings and the app reflects the new format throughout
  3. User can toggle between Light, Dark, and System themes from Settings and the change takes effect immediately
  4. User can click "Delete All Transactions" in Settings, confirm via a modal, and have all transactions removed
  5. User sees non-functional Notification Preferences toggles (email, budget alerts, newsletter) as placeholders in Settings
**Plans**: TBD

### Phase 7: Polish
**Goal**: The app looks and works correctly on every device and in both light and dark mode, with consistent design tokens, toast feedback, and skeleton loading states throughout
**Depends on**: Phase 6
**Requirements**: DESGN-01, DESGN-02, DESGN-03, DESGN-04, DESGN-05, DESGN-06, DESGN-07, DESGN-08
**Success Criteria** (what must be TRUE):
  1. App uses consistent color tokens (Teal #208E95 primary, Warm Gray #5E5240 secondary, Cream #FCFCF9 background, Charcoal #1F2121 dark) across all pages with no hardcoded hex values in component files
  2. Dark mode is fully applied via Tailwind dark: classes — no component shows unthemed colors when dark mode is active
  3. On mobile (375px viewport), sidebar collapses and is accessible via a hamburger menu; all interactive elements meet 48px minimum tap target size
  4. Transaction table collapses to a card-list layout on mobile; charts render at full width on mobile and in a 2-column grid on desktop
  5. Toast notifications appear for every user-initiated action (category update, insights generated, errors); skeleton loading screens appear for all data-heavy regions before data loads
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation | 5/5 | Complete   | 2026-02-27 |
| 2. Dashboard | 3/5 | In Progress|  |
| 3. Transactions | 0/TBD | Not started | - |
| 4. Analytics | 0/TBD | Not started | - |
| 5. Insights | 0/TBD | Not started | - |
| 6. Budgets + Settings | 0/TBD | Not started | - |
| 7. Polish | 0/TBD | Not started | - |
