# Feature Research

**Domain:** Personal finance dashboard — CSV-import, AI-categorized transactions, analytics, AI insights
**Researched:** 2026-02-26
**Confidence:** HIGH (table stakes and anti-features), MEDIUM (differentiators — validated against public fintech UX literature and the existing backend API surface)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete or broken.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Summary cards on dashboard (total income, total expenses, net balance, savings rate) | Every personal finance tool shows these KPIs at a glance; users land here first | LOW | Backend `/analytics/dashboard` returns these values. 4-card grid: income / expenses / net / savings rate. Include MoM delta indicator (▲ / ▼ + %) on each card |
| Spending-by-category pie chart | Users need to know where money goes; pie is the universal mental model for proportion | LOW | Backend `/analytics/categories` returns top-N categories. Keep to top 6–8 categories + "Other" bucket to avoid tiny slices |
| Monthly trend line chart | Users want to see spending trajectory over time | MEDIUM | Backend `/analytics/spending` returns monthly data. Show income vs expenses dual-line or bars; avoid area charts that hide the gap |
| Recent transactions widget on dashboard | Users expect a "what happened lately" preview without going to Transactions | LOW | 5–10 most recent transactions. Show merchant, amount, category badge, date. Link to full Transactions page |
| Full transactions table with pagination | Core utility: reviewing every transaction | MEDIUM | Offset-based pagination (25/page default). Backend supports `offset`+`limit`. Right-align amounts for scannability (UX rule: numeric columns right-aligned) |
| Transaction search by merchant/description | Users look up specific merchants constantly | LOW | Backend `TransactionFilters` supports `merchant` filter. Debounced input (300ms), clear button when active |
| Filter by date range | Users compare periods (this month vs last month) | LOW | Date range picker. Pre-set shortcuts: This month, Last month, Last 3 months, Last 6 months, This year |
| Filter by category | Users audit specific spending buckets | LOW | Multi-select dropdown. Backend supports `category` filter |
| Category edit modal (single transaction) | AI categorization is imperfect; users must correct it | MEDIUM | Modal with category dropdown. PATCH `/transactions/{id}`. Show current category as pre-selected. Close on confirm |
| Bulk category reassignment | Correcting many transactions in one shot | MEDIUM | Checkbox column, "Select all on page" + individual. Sticky bulk action bar appears on selection. PATCH `/transactions/batch`. Confirmation for destructive actions |
| Bulk delete | Users want to remove junk/duplicates efficiently | MEDIUM | DELETE `/transactions/batch`. Requires confirmation modal showing count ("Delete 12 transactions?") |
| Loading skeleton screens | Users perceive faster load when layout appears before data | LOW | shadcn Skeleton component. One skeleton variant per card type (summary card, table row, chart placeholder). Use wave animation |
| Empty states on all pages | New users or empty date ranges must see guidance, not blank whitespace | LOW | Contextual message + CTA. "No transactions yet — upload a CSV to get started" with Upload button. "No transactions match your filters" with Clear Filters button |
| Toast notifications for actions | Confirmation that batch delete, category edit, CSV upload worked | LOW | shadcn Toast. Variants: success (green), error (red), info (teal). 4-second auto-dismiss. Undo not required given backend has no undo endpoint |
| Error boundaries per page section | API failures should not crash the whole page | LOW | React error boundary per major section (charts, table, summary cards). Show inline "Something went wrong — try again" with retry button |
| Responsive layout (collapsible sidebar) | Finance apps are checked on phones — mobile is not optional | HIGH | Sidebar collapses to hamburger on <768px. shadcn Sidebar already has collapsible support. 48px minimum tap targets for all interactive elements |
| AI insights callout on dashboard | Users expect a taste of AI value without navigating away | LOW | Single highlighted insight card on dashboard. Shows most relevant insight from the insights cache. Links to Insights page |
| Insights page with insight cards | AI-generated explanations of spending patterns are a core value proposition | MEDIUM | Card grid (2-col desktop, 1-col mobile). Categories: spending / recurring / savings / anomalies / comparisons. Show generated_at timestamp |
| Regenerate insights button with cooldown | Backend rate-limits; UI must prevent repeated hammering | LOW | Button disabled during cooldown (show countdown timer). No backend cooldown endpoint — implement 60s client-side cooldown via localStorage timestamp |
| Analytics — spending by category tab | Deep-dive version of dashboard pie; with trend per category | MEDIUM | Bar chart (horizontal) ranked by spend. Show % of total. Use `/analytics/categories` |
| Analytics — income vs expenses tab | Users want to track surplus/deficit trend clearly | MEDIUM | Dual-line or grouped bar chart per month. Use `/analytics/spending` |
| Analytics — month-over-month tab | Users track whether they're improving or worsening | MEDIUM | Bar chart with MoM delta. Highlight months above/below average |
| Analytics — seasonality tab | Behavioral patterns (day of week, month of year) are genuinely surprising and useful | MEDIUM | Heatmap or bar chart for day-of-week spend. Use `/analytics/behavior` |
| Budgets page placeholder | Navigation item is already expected; blank page is better than 404 | LOW | "Coming Soon" card. Do not wire to any API. Include teal accent to match brand |
| Dark mode support | Design system specifies charcoal dark mode; users toggle in system settings | MEDIUM | Tailwind `dark:` classes. Follow charcoal (#1F2121) background. Chart colors must pass WCAG 4.5:1 contrast in both modes |
| EUR currency formatting | User is in Berlin; EUR is the correct default | LOW | `Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' })`. Apply consistently in all cards, tables, and charts |

---

### Differentiators (Competitive Advantage)

Features that set this product apart from generic finance trackers. These are the AI-native, insight-forward capabilities that justify building custom rather than using Mint/YNAB.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| AI insights by category (spending / recurring / savings / anomalies / comparisons) | Users get specific, actionable observations — not generic advice | HIGH | Backend already generates these via the insights agent. UI must present them as distinct card types with visual differentiation (icon + color accent per category). Display confidence or context where available |
| Anomaly callout card | Most apps don't surface outlier transactions automatically — this is genuinely useful | MEDIUM | Use `/analytics/anomalies` data. Show "This month you spent 3x your usual on Dining" style cards. Color: amber/warning accent |
| Savings tracker on Insights page | Visualizing net savings over time motivates behavior change; progress bar > number | MEDIUM | Derived from income - expenses per month. Simple bar chart or progress bar showing savings rate trend over last 6 months. No goal-setting needed (no backend for it) |
| Spending stability classification | Showing "stable" vs "volatile" categories helps users understand predictability | MEDIUM | Data from `/analytics/behavior` (volatility classification). Badge on category rows: "Stable" / "Volatile". Tooltip with explanation |
| Recurring expenses tracker | Hidden subscriptions surface automatically — high perceived value | MEDIUM | Data from `/analytics/recurring`. Show total monthly recurring cost, list of recurring merchants with frequency. Flag new recurring charges |
| Merchant concentration risk indicator | Shows when a user relies heavily on a single merchant — surprising and useful | LOW | From `/analytics/merchants` concentration metric. Simple callout: "30% of your spending goes to 3 merchants" |
| Confidence score badge on transactions | Surfaces AI categorization quality so users know which categories to double-check | LOW | Show confidence_score from transaction data. Badge: "High confidence" (green, ≥0.85) / "Review suggested" (amber, <0.85). Only show amber badges to reduce noise |
| Contextual empty state CTAs | Smart empty states guide users toward actions instead of showing generic blank states | LOW | Upload CSV CTA for users with no transactions. "Try expanding the date range" for filtered views with no results. Context-aware vs generic |
| Date range filter persisted in URL params | Users can bookmark or share a specific time window | LOW | `useSearchParams` + router.replace to sync filters to URL. No backend change needed |

---

### Anti-Features (Commonly Requested, Often Problematic)

Features to explicitly not build. They consume engineering time, add complexity, and provide marginal value for a small-group app.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time bank connection (Plaid/TrueLayer) | "I don't want to upload CSVs manually" | OAuth bank integrations require compliance agreements, per-institution maintenance, costs scale per user, and are blocked by the project constraint (backend finalized). Backend has no bank connection API | Optimize CSV upload UX: drag-and-drop, clear mapping UI, fast confirmation flow. The existing 2-step upload pipeline is already good |
| Budget creation and goal management | Users want to set budgets | No backend budget API exists; building a fake client-side budget is a lie that breaks when data loads from server. Creates false expectations | Budgets page as "Coming Soon" placeholder. Deliver budgets in a future milestone when backend is ready |
| Natural language / chatbot UI | "Ask AI anything about my finances" | Backend has a chatbot agent but it is explicitly out of scope for this milestone. Building a chat UI without proper session handling creates UX debt | Surface AI insights through the structured Insights page instead. The insights agent already provides queryable analysis |
| Infinite scroll for transactions | Feels modern and fluid | In finance, users need to find specific transactions; infinite scroll breaks "where was that charge?" navigation. Users lose their place. Pagination with page number is better for reference tasks | Classic numbered pagination (25/page). Allow URL-based page param so users can return to their position |
| Per-row edit inline (spreadsheet-style editing) | Power users want fast edits | Complex to implement correctly (focus management, optimistic updates, conflict resolution). shadcn Table is not a spreadsheet. Adds significant test surface | Modal-based category edit is the correct scope. Edit one field (category) via modal — that covers 90% of user correction needs |
| CSV export / download all data | "I want to export my data" | PROJECT.md explicitly lists "Download all data endpoint" as out of scope (no backend endpoint). Placeholder UI that downloads nothing is misleading | "Coming Soon" export button if navigation demands it, or omit entirely |
| Multi-currency support | Users transact in multiple currencies | Backend stores amount as float with no currency field. EUR is the implicit default. Adding multi-currency UI without backend support produces incorrect conversions | Lock to EUR. Display foreign transactions at their EUR amount as-is (bank already converts before export) |
| Drag-and-drop chart customization | Dashboard personalization | This is a SaaS-grade feature. For a small group app, the correct defaults are sufficient. Adds state management complexity with no clear benefit | Fixed dashboard layout with sensible defaults. Good defaults > infinite configurability |
| Notification/alert system (email, push) | "Alert me when I overspend" | Requires backend notification infrastructure (none exists). Push notifications require service workers. Email requires an email service. All out of scope | Surface anomaly alerts on the Insights page as pull (user views) rather than push (system notifies) |
| Multi-user household view / shared accounts | "My partner and I want to see combined spending" | Clerk handles auth per-user. Backend data is siloed by user_id. Merging requires backend API changes which are explicitly out of scope | Each user has their own account. Small-group app: each person maintains their own data |
| Transaction split (allocate one transaction to multiple categories) | "My Costco trip was 60% food, 40% household" | High complexity — requires new data model, UI for splitting amounts, recalculation across all analytics. No backend support | Single category per transaction. Users can rename the description for context |
| Zebra striping on transaction table | "Easier to scan rows" | Creates five semantic color levels when combined with hover state, selection state, and dark mode. Visual confusion, not clarity | Subtle row hover highlight only. 1px light separator between rows is sufficient |

---

## Feature Dependencies

```
[Summary Cards]
    └──requires──> [/analytics/dashboard API]

[Category Pie Chart]
    └──requires──> [/analytics/categories API]

[Monthly Trend Chart]
    └──requires──> [/analytics/spending API]

[Bulk Category Reassign]
    └──requires──> [Transaction Table with Checkboxes]
                       └──requires──> [/transactions/batch PATCH]

[Bulk Delete]
    └──requires──> [Transaction Table with Checkboxes]
                       └──requires──> [/transactions/batch DELETE]

[Category Edit Modal]
    └──requires──> [/transactions/{id} PATCH]

[AI Insights Callout on Dashboard]
    └──requires──> [Insights Page]
                       └──requires──> [/insights GET]

[Savings Tracker]
    └──requires──> [/analytics/spending monthly data]

[Anomaly Callout]
    └──requires──> [/analytics/anomalies]

[Recurring Tracker]
    └──requires──> [/analytics/recurring]

[Seasonality Tab]
    └──requires──> [/analytics/behavior]

[Dark Mode]
    └──enhances──> [All visual components]

[Skeleton Screens]
    └──enhances──> [All data-fetching components]

[URL Filter Persistence]
    └──enhances──> [Transaction Table filters]
```

### Dependency Notes

- **Bulk actions require checkbox column:** The transaction table must render checkboxes before bulk action UI can be activated. Build them together in one phase, not sequentially.
- **Dashboard insights callout requires Insights page:** The callout links to Insights page. If Insights page ships after Dashboard, the callout should link to a coming-soon state or be deferred to the same phase.
- **All analytics tabs are independent:** Each tab uses a different API endpoint. They can ship independently but are best delivered as a single tabbed page to avoid partial-feeling UX.
- **Savings tracker derives from spending data:** No separate API needed. Calculate from `/analytics/spending` monthly income vs expense deltas. Keep the calculation client-side.

---

## MVP Definition

### Launch With (v1) — This Milestone

Minimum viable set to make the app usable as a daily finance tool.

- [ ] Dashboard page: 4 summary cards + pie chart + line chart + recent transactions widget + AI insights callout — users land here; it must show value immediately
- [ ] Transactions page: paginated table with search, date range filter, category filter, single-transaction category edit modal — core audit and correction workflow
- [ ] Transactions page: bulk category reassign + bulk delete — power workflows that make CSV imports actually manageable
- [ ] Analytics page: all 4 tabs (spending by category, income vs expenses, MoM trends, seasonality) — this is the depth that justifies the app
- [ ] Insights page: insight cards grid + savings tracker + regenerate button with cooldown — the AI value proposition made visible
- [ ] Budgets page: placeholder "Coming Soon" — prevents 404 on nav item
- [ ] Responsive layout: sidebar collapses on mobile, 48px tap targets throughout
- [ ] Skeleton screens on all data-fetching components
- [ ] Empty states on all pages with contextual CTAs
- [ ] Toast notifications for all user-initiated mutations
- [ ] EUR currency formatting throughout
- [ ] Dark mode via Tailwind `dark:` classes

### Add After Validation (v1.x) — Post-Launch

- [ ] Confidence score badges on transaction rows — useful but not blocking; needs user feedback on whether the threshold feels right
- [ ] URL-persisted filter state — quality-of-life; add when users report losing their filter context
- [ ] Merchant concentration risk callout — small feature, deferred to avoid scope creep this milestone
- [ ] Spending stability (stable/volatile) category badges — deferred; requires user testing to confirm it adds clarity vs noise

### Future Consideration (v2+)

- [ ] Budget creation API + budget page — new backend milestone required first
- [ ] CSV export endpoint — backend endpoint does not exist; cannot ship without it
- [ ] Bank connection via open banking API — compliance, cost, and backend work required

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Dashboard summary cards | HIGH | LOW | P1 |
| Category pie chart | HIGH | LOW | P1 |
| Monthly trend line chart | HIGH | MEDIUM | P1 |
| Recent transactions widget | HIGH | LOW | P1 |
| AI insights callout (dashboard) | HIGH | LOW | P1 |
| Transactions table (paginated) | HIGH | MEDIUM | P1 |
| Search + filter (date, category) | HIGH | LOW | P1 |
| Skeleton screens | HIGH | LOW | P1 |
| Empty states with CTAs | HIGH | LOW | P1 |
| Responsive sidebar | HIGH | MEDIUM | P1 |
| Category edit modal | HIGH | MEDIUM | P1 |
| Bulk category reassign | HIGH | MEDIUM | P1 |
| Bulk delete | HIGH | LOW | P1 |
| Insights page (card grid) | HIGH | MEDIUM | P1 |
| Savings tracker | MEDIUM | LOW | P1 |
| Regenerate button + cooldown | MEDIUM | LOW | P1 |
| Analytics — spending by category tab | HIGH | MEDIUM | P1 |
| Analytics — income vs expenses tab | HIGH | MEDIUM | P1 |
| Analytics — MoM trends tab | HIGH | MEDIUM | P1 |
| Analytics — seasonality tab | MEDIUM | MEDIUM | P1 |
| Toast notifications | MEDIUM | LOW | P1 |
| EUR formatting | HIGH | LOW | P1 |
| Dark mode | MEDIUM | MEDIUM | P1 |
| Budgets placeholder | LOW | LOW | P1 |
| Confidence score badge | MEDIUM | LOW | P2 |
| URL filter persistence | MEDIUM | LOW | P2 |
| Anomaly callout card | MEDIUM | LOW | P2 |
| Recurring expenses tracker | MEDIUM | MEDIUM | P2 |
| Merchant concentration risk | LOW | LOW | P2 |
| Spending stability badges | LOW | LOW | P3 |

**Priority key:**
- P1: Must have for this milestone launch
- P2: Add in first iteration after launch
- P3: Future consideration

---

## Competitor Feature Analysis

Reference apps: Mint (sunset), YNAB, Actual Budget, Money Dashboard (UK)

| Feature | Mint / YNAB | Actual Budget | Our Approach |
|---------|-------------|---------------|--------------|
| Transaction table | Infinite scroll | Paginated | Paginated — finance is reference, not feed |
| Category editing | Inline edit in row | Modal | Modal — less error-prone, clear intent |
| Charts | Recharts-based, static tooltips | Minimal | TanStack React Charts with hover tooltips |
| AI insights | None (Mint) / rule-based (YNAB) | None | LLM-generated, categorized by insight type |
| Mobile | Native app | Web-first (responsive) | Web-first responsive — matches our delivery target |
| Bulk actions | Category reassign only (Mint) | Full bulk (Actual) | Full bulk (delete + category reassign) |
| Empty states | Generic | Contextual | Contextual with action CTAs |
| Savings tracker | Goal-based with manual input | Budget-based | Derived automatically from income - expenses |
| Anomaly detection | Rule-based alerts | None | AI-detected via z-score, surfaced in Insights |
| Dark mode | Partial (Mint discontinued) | Yes | Yes — design system specifies charcoal mode |

---

## Mobile UX Considerations (Finance Data Specifically)

Finance data on mobile presents specific challenges that are distinct from generic responsive design.

**Transaction Table on Mobile**
- Full table with 6+ columns does not fit on 375px wide screens. Pattern: collapse to a card list on mobile. Show merchant name, amount (large, right-aligned), category badge, date. Hide description column.
- Bulk selection on mobile: tap row to enter selection mode (long-press or tap checkbox), then secondary row taps add to selection. Avoid accidental selections.
- Filter panel: use a bottom sheet (slide-up modal) rather than a sidebar or inline dropdowns. Full-screen filter overlay is the correct mobile pattern.

**Charts on Mobile**
- Pie charts become unreadable below 300px. Use a horizontal bar chart as the mobile fallback for category breakdowns. TanStack React Charts handles responsive sizing via container width.
- Line charts: allow horizontal scroll on mobile rather than squashing data points. Pinch-to-zoom is ideal but complex; horizontal scroll is sufficient.
- Touch targets on chart legends and data points: minimum 44px × 44px. TanStack charts allow custom tooltip trigger zones.

**Summary Cards on Mobile**
- 4-column grid becomes 2×2 grid on mobile. shadcn grid with `grid-cols-2 md:grid-cols-4`.
- Currency amounts must be legible at mobile font sizes: use 20px minimum for primary value, 12px for label.

**Insights Cards on Mobile**
- 2-column grid on desktop → 1-column on mobile. Cards should not truncate insight text; allow natural height expansion.
- Regenerate button: full-width on mobile for easy tap.

**Sidebar on Mobile**
- shadcn Sidebar has built-in Sheet (slide-in panel) mode for mobile. Use `useSidebar()` hook. Hamburger menu in top-left of header triggers it.
- Close sidebar on route change. Close on outside tap.

---

## Sources

- [Fintech UX Best Practices 2026 — Eleken](https://www.eleken.co/blog-posts/fintech-ux-best-practices)
- [Data Table Design UX Patterns — Pencil & Paper](https://www.pencilandpaper.io/articles/ux-pattern-analysis-enterprise-data-tables)
- [Designing a Better Bank Transaction List — Scott Herrington](https://www.scottherrington.com/blog/designing-a-better-bank-app-transaction-list/)
- [Best UX Design Practices for Finance Apps — G & Co.](https://www.g-co.agency/insights/the-best-ux-design-practices-for-finance-apps)
- [Bulk Actions UX — Eleken](https://www.eleken.co/blog-posts/bulk-actions-ux)
- [Skeleton Screens 101 — Nielsen Norman Group](https://www.nngroup.com/articles/skeleton-screens/)
- [Empty States Pattern — Carbon Design System](https://carbondesignsystem.com/patterns/empty-states-pattern/)
- [Mobile-First Banking UX Best Practices — Snowdrop](https://snowdropsolutions.com/mobile-first-banking-ux-best-practices-for-2025/)
- [AI and UX in Banking — Medium](https://medium.com/@birdzhanhasan_26235/research-on-ai-and-ux-in-banking-289ca2756c83)
- [15 Filter UI Patterns That Actually Work — Bricx Labs](https://bricxlabs.com/blogs/universal-search-and-filters-ui)
- [Why Table Pagination Matters — Alf Design Group](https://www.alfdesigngroup.com/post/why-pagination-is-important-for-table-design)
- [Personal Finance Apps: What Users Expect in 2025 — WildNetEdge](https://www.wildnetedge.com/blogs/personal-finance-apps-what-users-expect-in-2025)

---

*Feature research for: Personal finance dashboard UI (Next.js frontend, FastAPI backend)*
*Researched: 2026-02-26*
