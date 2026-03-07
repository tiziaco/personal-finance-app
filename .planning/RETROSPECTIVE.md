# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-03
**Phases:** 7 | **Plans:** 29 | **Timeline:** 11 days (2026-02-21 → 2026-03-03)

### What Was Built

- **Foundation**: Typed API layer (3 type files, authenticated API client, 5 React Query hooks) with Clerk JWT and stale-time ladder
- **Dashboard**: Full financial overview page — welcome card, 4 summary cards, spending pie + trend charts, recent transactions, AI insights callout
- **Transactions**: Filterable/searchable TanStack Table with server-side pagination, category edit modal, and bulk recategorize
- **Analytics**: 4-tab lazy-loaded analytics (spending by category, income vs expenses, MoM trends, seasonality) with visitedTabs pattern
- **Insights**: AI insight cards in 5 category tabs, savings tracker checklist, 1-hour localStorage cooldown generate button
- **Budgets + Settings**: Budgets placeholder, currency/date format providers, dark mode toggle, delete-all-transactions
- **Polish**: Semantic OKLCH tokens, full dark mode, mobile hamburger sidebar, 48px tap targets, mobile card-list, universal toast + skeleton coverage

### What Worked

- **Shadow-import hook pattern** (currency/date format): Zero JSX changes at migration call sites — extremely clean for retroactive adoption
- **visitedTabs Set lazy-load**: Analytics tabs only fetch on first activation — no extra complexity and correct by construction
- **Wave-based parallelization**: Plans 04-01 and 04-02 ran in parallel; saved meaningful time on analytics
- **Gap closure phases within milestones**: Phases 04 and 05 included explicit gap-closure plans (04-04, 04-05, 05-03) — bugs were named and tracked rather than silently patched
- **RESEARCH.md for non-obvious API shapes**: Documenting backend field shapes (monthly_trend, pct_change semantics) prevented integration bugs in later plans
- **stale-time ladder**: Proportional to compute cost — avoids over-fetching insights/analytics while keeping transactions fresh

### What Was Inefficient

- **ROADMAP.md Phase 1 never updated with plan list**: "Plans: TBD" remained throughout the entire milestone — minor but visible debt
- **Charts library pivot**: Switched from TanStack React Charts (user-specified) to shadcn Chart (Recharts) — earlier SSR research would have surfaced this before roadmap was created
- **STATE.md accuracy drift**: Current focus stayed at "Phase 4 — Analytics" even after Phase 7 completed; milestone_name left as generic "milestone"
- **REQUIREMENTS.md checkbox drift**: DESGN-07, DESGN-08, FOUND-03 checkboxes not updated even as traceability table said Complete — created end-of-milestone confusion

### Patterns Established

- **amount as string**: Python Decimal → JSON string; never number in TypeScript; parse only at render
- **getToken() inside queryFn**: Not in queryKey — Clerk token is unstable; correct React Query v5 + Clerk pattern
- **shadow-import hooks**: `const formatCurrency = useFormatCurrency()` at call site — enables zero-JSX migration of formatting utilities
- **Chart color vars**: `var(--chart-N)` not `hsl(var(--chart-N))` — Tailwind v4 OKLCH values need bare CSS var syntax
- **ErrorBoundary per tab/section**: Each analytics tab wrapped independently — chart error in one tab doesn't crash the page

### Key Lessons

1. **Run chart library SSR compatibility check before roadmap phase 1** — finding TanStack React Charts had SSR issues after roadmap was set required a swap; this should be in the pre-roadmap research checklist
2. **Keep REQUIREMENTS.md checkboxes in sync at plan completion** — the traceability table was accurate but checkboxes drifted; an end-of-phase reminder to tick checkboxes would eliminate milestone confusion
3. **State file `current_focus` should be updated at each phase completion** — stale focus values reduce STATE.md utility for session handoffs
4. **Gap-closure plans (X.Y decimal numbering) are very effective** — naming bugs as explicit plans with requirements IDs kept the phase goal clean and made verification straightforward

### Cost Observations

- Model mix: balanced profile (sonnet for execution, haiku for quick tasks)
- Sessions: multiple across 11 days
- Notable: Phase 7 Polish was surprisingly fast — semantic token + dark mode work was mostly additive; the main challenge was the mobile sidebar integration

---

## Cross-Milestone Trends

| Metric | v1.0 |
|--------|------|
| Phases | 7 |
| Plans | 29 |
| LOC (TS/TSX) | ~8,255 |
| Timeline (days) | 11 |
| Files changed | 262 |
| Gap-closure plans | 3 (04-04, 04-05, 05-03) |
