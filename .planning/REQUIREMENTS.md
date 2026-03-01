# Requirements: Personal Finance Dashboard

**Defined:** 2026-02-27
**Core Value:** Users can understand where their money goes — at a glance on the dashboard, and in depth through analytics and AI insights — without any manual data entry beyond uploading a CSV.

## v1 Requirements

### Foundation

- [x] **FOUND-01**: Typed TypeScript interfaces exist for all backend API response shapes (transactions, analytics, insights, dashboard summary)
- [x] **FOUND-02**: A typed API client module exists with authenticated fetch functions using Clerk JWT tokens for all backend endpoints
- [ ] **FOUND-03**: React Query hooks exist for all data needs: useTransactions (paginated + filtered), useDashboardSummary, useAnalytics (per endpoint), useInsights, useCategories
- [x] **FOUND-04**: Shared chart wrapper components exist (pie chart, line chart, bar chart) using shadcn/ui Chart (Recharts), with SSR-safe rendering and consistent design tokens
- [x] **FOUND-05**: Shared skeleton components exist for all data-bearing UI regions (cards, tables, charts, insight cards)
- [x] **FOUND-06**: Error boundary components exist and are applied to all pages and major sections

### Dashboard

- [x] **DASH-01**: User sees a welcome card with their name and total spending this month
- [x] **DASH-02**: User sees 4 summary cards: Total Spent This Month, Remaining Budget, Recurring Costs, Savings Goal Progress — with color coding (green positive, red overspend)
- [x] **DASH-03**: User sees a spending-by-category pie chart (top 5 categories, interactive with legend and percentages)
- [x] **DASH-04**: User sees a 6-month spending trend line chart with current month highlighted and hover tooltips
- [x] **DASH-05**: User sees a recent transactions widget showing the last 5-10 transactions (date, merchant, amount, category) with a "View All" link
- [x] **DASH-06**: User sees an AI insights callout showing 1-2 most important highlights, with a "Generate New Insights" CTA and a badge when new transaction data has been added since last generation
- [x] **DASH-07**: User can click "Upload CSV" primary CTA from the dashboard to reach the upload flow
- [x] **DASH-08**: User can click "View Insights" secondary CTA to navigate to the Insights page

### Transactions

- [x] **TXN-01**: User can search transactions by merchant name with real-time filtering
- [x] **TXN-02**: User can filter transactions by date range (start/end date picker)
- [x] **TXN-03**: User can filter transactions by category (dropdown showing all available categories)
- [x] **TXN-04**: User can filter transactions by amount range (min/max input or slider)
- [x] **TXN-05**: User can sort transactions by date (newest first default), amount (high to low), or merchant (A-Z)
- [x] **TXN-06**: User sees a paginated transaction table (25 per page) with columns: Checkbox, Date, Merchant, Amount, Category, Confidence Score, Actions
- [x] **TXN-07**: User can navigate between pages with "Previous / Page X of Y / Next" controls and a "Showing X-Y of Z transactions" count
- [x] **TXN-08**: User can click a transaction's category or edit button to open a category edit modal (shows merchant, amount, date; dropdown for new category; save/cancel)
- [x] **TXN-09**: User can select multiple transactions via checkbox and bulk-recategorize them
- [x] **TXN-10**: User sees an empty state with illustration and "Upload a CSV file to get started" CTA when no transactions exist

### Analytics

- [x] **ANLT-01**: User sees an Analytics page with tabbed navigation (shadcn Tabs component) for each analytics dimension
- [x] **ANLT-02**: User can view spending by category tab with pie/bar chart and quick date filters (1M / 3M / 6M)
- [x] **ANLT-03**: User can view income vs expenses tab showing a bar chart by month with a cash flow summary
- [x] **ANLT-04**: User can view month-over-month trends tab with a line chart comparing spending across months
- [x] **ANLT-05**: User can view seasonality tab showing spending patterns by month of year and day of week (bar chart or heatmap)
- [x] **ANLT-06**: Analytics tabs lazy-load their data only when the tab becomes active (not all on mount)

### Insights

- [ ] **INSGT-01**: User sees a prominent "Generate New Insights" button at the top of the Insights page
- [ ] **INSGT-02**: User sees a loading spinner and disabled button state while insights are generating
- [ ] **INSGT-03**: The Generate button is disabled with a countdown timer ("Refreshes in XX minutes") for 1 hour after last generation
- [ ] **INSGT-04**: User sees insight cards organized by category (Spending Patterns, Recurring Charges, Savings Opportunities, Anomalies, Comparisons) — implemented as tabs or accordion
- [ ] **INSGT-05**: Each insight card shows: title, icon, description (2-3 sentences), a highlighted key metric, an optional action CTA, and a "Generated at [time]" timestamp
- [ ] **INSGT-06**: User sees a savings tracker showing total potential monthly savings across all actionable insights, with a checkbox list to mark recommendations as done
- [ ] **INSGT-07**: User sees an empty state with illustration and "Generate Insights" CTA when no insights have been generated yet

### Budgets

- [ ] **BUDG-01**: User sees a Budgets page with a prominent "Coming Soon" message and brief description of what budgets will offer

### Settings Enhancements

- [ ] **SETT-01**: User can set currency preference (dropdown: EUR default, plus USD, GBP, etc.) in Settings
- [ ] **SETT-02**: User can set date format preference (DD/MM/YYYY default, plus MM/DD/YYYY, YYYY-MM-DD)
- [ ] **SETT-03**: User can toggle theme between Light / Dark / System from Settings
- [ ] **SETT-04**: User can delete all transactions from Settings (red button requiring confirmation modal)
- [ ] **SETT-05**: User sees placeholder Notification Preferences toggles (email, budget alerts, newsletter — non-functional in v1)

### Design System & Responsiveness

- [ ] **DESGN-01**: App uses consistent color tokens: Teal (#208E95) primary, Warm Gray (#5E5240) secondary, Cream (#FCFCF9) light background, Charcoal (#1F2121) dark mode background, Red (#C01527) overspend alerts, Green (#208E95) savings
- [ ] **DESGN-02**: App supports full dark mode with Tailwind CSS dark: classes applied throughout all pages and components
- [ ] **DESGN-03**: Desktop layout has a collapsible sidebar; mobile layout has a hamburger menu that opens the sidebar as an overlay or drawer
- [ ] **DESGN-04**: All interactive elements have minimum 48px tap targets on mobile
- [ ] **DESGN-05**: Charts render at full width on mobile, 2-column grid on desktop
- [ ] **DESGN-06**: Transaction table collapses to a card-list layout at mobile breakpoints
- [ ] **DESGN-07**: Toast notifications appear for all user-initiated actions (category update, insights generated, errors)
- [ ] **DESGN-08**: Skeleton loading screens appear for all data-heavy regions before data loads

## v2 Requirements

### Transactions

- **TXN-V2-01**: Bulk export transactions to CSV (export endpoint not available in current backend)
- **TXN-V2-02**: Click merchant name to filter table to only that merchant's transactions

### Insights

- **INSGT-V2-01**: Track "realized savings" when user marks insight recommendations as completed over time

### Dashboard

- **DASH-V2-01**: Click spending category in pie chart to jump to filtered Transactions view for that category

### Budgets

- **BUDG-V2-01**: Full budget creation and management (requires backend budget API)

### Settings

- **SETT-V2-01**: Download all data (no backend endpoint available currently)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Modifying `/server` backend | Backend finalized — frontend consumes only |
| Budget creation UI | No backend budget API available; placeholder only |
| CSV export from Transactions | Backend endpoint not available in v1 |
| Real-time chatbot UI | Backend agent exists but not in this milestone's scope |
| OAuth login | Clerk handles auth, not in scope |
| Mobile native app | Web-first |
| Inline row editing (spreadsheet style) | Anti-pattern for finance data; modal is correct UX |
| Infinite scroll on transactions | Breaks navigation back to specific row; pagination is correct |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| FOUND-01 | Phase 1 — Foundation | Complete |
| FOUND-02 | Phase 1 — Foundation | Complete |
| FOUND-03 | Phase 1 — Foundation | Pending |
| FOUND-04 | Phase 1 — Foundation | Complete |
| FOUND-05 | Phase 1 — Foundation | Complete |
| FOUND-06 | Phase 1 — Foundation | Complete |
| DASH-01 | Phase 2 — Dashboard | Complete |
| DASH-02 | Phase 2 — Dashboard | Complete |
| DASH-03 | Phase 2 — Dashboard | Complete |
| DASH-04 | Phase 2 — Dashboard | Complete |
| DASH-05 | Phase 2 — Dashboard | Complete |
| DASH-06 | Phase 2 — Dashboard | Complete |
| DASH-07 | Phase 2 — Dashboard | Complete |
| DASH-08 | Phase 2 — Dashboard | Complete |
| TXN-01 | Phase 3 — Transactions | Complete |
| TXN-02 | Phase 3 — Transactions | Complete |
| TXN-03 | Phase 3 — Transactions | Complete |
| TXN-04 | Phase 3 — Transactions | Complete |
| TXN-05 | Phase 3 — Transactions | Complete |
| TXN-06 | Phase 3 — Transactions | Complete |
| TXN-07 | Phase 3 — Transactions | Complete |
| TXN-08 | Phase 3 — Transactions | Complete |
| TXN-09 | Phase 3 — Transactions | Complete |
| TXN-10 | Phase 3 — Transactions | Complete |
| ANLT-01 | Phase 4 — Analytics | Complete |
| ANLT-02 | Phase 4 — Analytics | Complete |
| ANLT-03 | Phase 4 — Analytics | Complete |
| ANLT-04 | Phase 4 — Analytics | Complete |
| ANLT-05 | Phase 4 — Analytics | Complete |
| ANLT-06 | Phase 4 — Analytics | Complete |
| INSGT-01 | Phase 5 — Insights | Pending |
| INSGT-02 | Phase 5 — Insights | Pending |
| INSGT-03 | Phase 5 — Insights | Pending |
| INSGT-04 | Phase 5 — Insights | Pending |
| INSGT-05 | Phase 5 — Insights | Pending |
| INSGT-06 | Phase 5 — Insights | Pending |
| INSGT-07 | Phase 5 — Insights | Pending |
| BUDG-01 | Phase 6 — Budgets + Settings | Pending |
| SETT-01 | Phase 6 — Budgets + Settings | Pending |
| SETT-02 | Phase 6 — Budgets + Settings | Pending |
| SETT-03 | Phase 6 — Budgets + Settings | Pending |
| SETT-04 | Phase 6 — Budgets + Settings | Pending |
| SETT-05 | Phase 6 — Budgets + Settings | Pending |
| DESGN-01 | Phase 7 — Polish | Pending |
| DESGN-02 | Phase 7 — Polish | Pending |
| DESGN-03 | Phase 7 — Polish | Pending |
| DESGN-04 | Phase 7 — Polish | Pending |
| DESGN-05 | Phase 7 — Polish | Pending |
| DESGN-06 | Phase 7 — Polish | Pending |
| DESGN-07 | Phase 7 — Polish | Pending |
| DESGN-08 | Phase 7 — Polish | Pending |

**Coverage:**
- v1 requirements: 51 total
- Mapped to phases: 51
- Unmapped: 0 ✓

---
*Requirements defined: 2026-02-27*
*Last updated: 2026-02-27 — traceability populated after roadmap creation*
