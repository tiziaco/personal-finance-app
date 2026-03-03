---
phase: 05-insights
plan: 01
subsystem: ui
tags: [react, nextjs, lucide, react-query, localStorage, insights]

# Dependency graph
requires:
  - phase: 05-insights
    provides: types/insights.ts, hooks/use-insights.ts (from foundation phase)
provides:
  - SECTION_CONFIG mapping 5 display categories to backend section values
  - INSIGHT_ICON_MAP mapping InsightType to Lucide icons
  - getCategoryForInsight, getInsightsForCategory, getKeyMetric, getCTAForInsight helpers
  - GenerateButton with React Query refetch and 1-hour localStorage cooldown
  - InsightCard rendering icon, title, description, key metric, CTA, and generated timestamp
affects: [05-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - SECTION_CONFIG as const array with filter predicate per category for flexible insight grouping
    - localStorage cooldown pattern with SSR-safe hydration for rate-limiting UI actions
    - Shared generatedAt prop pattern — response-level timestamp passed to each card (not per-insight field)

key-files:
  created:
    - web-app/src/lib/insights-helpers.ts
    - web-app/src/components/insights/generate-button.tsx
    - web-app/src/components/insights/insight-card.tsx
  modified: []

key-decisions:
  - "SECTION_CONFIG uses filter predicate for savings_opportunities — backend has no savings section; derived from subscriptions where monthly_cost is number"
  - "formatCurrency inlined in insights-helpers.ts — formatCurrency not present in @/lib/utils (only cn exists)"
  - "GenerateButton manages all state internally (no props) — self-contained component for clean composition in Plan 02"
  - "InsightCard receives generatedAt from parent (InsightsResponse envelope) — Insight type has no per-insight timestamp field"

patterns-established:
  - "Insights category filtering: SECTION_CONFIG.sections match + optional filter predicate applied in getInsightsForCategory"
  - "Cooldown hydration: localStorage.getItem on mount only (typeof window guard), setInterval ticks every 30s"

requirements-completed: [INSGT-01, INSGT-02, INSGT-03, INSGT-04, INSGT-05]

# Metrics
duration: 2min
completed: 2026-03-02
---

# Phase 5 Plan 01: Insights Building Blocks Summary

**Three foundational Insights components: helpers module with SECTION_CONFIG/metric extraction, GenerateButton with 1-hour localStorage cooldown, and InsightCard rendering all insight fields**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-02T08:28:38Z
- **Completed:** 2026-03-02T08:30:05Z
- **Tasks:** 3
- **Files modified:** 3

## Accomplishments

- Created `insights-helpers.ts` with SECTION_CONFIG (5 display categories), INSIGHT_ICON_MAP, getCategoryForInsight, getInsightsForCategory, getKeyMetric, and getCTAForInsight
- Created `GenerateButton` with React Query refetch, 1-hour localStorage cooldown, SSR-safe hydration, and 3 button text states
- Created `InsightCard` rendering icon, summary title, narrative_analysis, key metric pill, optional CTA link, and shared generated timestamp

## Task Commits

Each task was committed atomically:

1. **Task 1: Create insights-helpers.ts** - `06d17d5` (feat)
2. **Task 2: Create GenerateButton component** - `b8ae699` (feat)
3. **Task 3: Create InsightCard component** - `ec64adc` (feat)

## Files Created/Modified

- `web-app/src/lib/insights-helpers.ts` - SECTION_CONFIG, INSIGHT_ICON_MAP, getCategoryForInsight, getInsightsForCategory, getKeyMetric, getCTAForInsight
- `web-app/src/components/insights/generate-button.tsx` - GenerateButton with cooldown logic, no props
- `web-app/src/components/insights/insight-card.tsx` - InsightCard rendering all required fields

## Decisions Made

- **SECTION_CONFIG filter predicate for savings_opportunities**: Backend has no "savings" section; derived from subscriptions where `supporting_metrics.monthly_cost` is a number. Uses filter function in SECTION_CONFIG entry.
- **formatCurrency inlined**: `@/lib/utils` only exports `cn`; no `formatCurrency` exists. Inlined `Intl.NumberFormat('de-DE', { style: 'currency', currency: 'EUR' })` in insights-helpers.ts.
- **GenerateButton is prop-less**: Self-contained component managing cooldown state internally for clean composition in Plan 02.
- **InsightCard receives generatedAt from parent**: `Insight` type has no per-insight timestamp; `generated_at` lives on `InsightsResponse` envelope and is passed as a prop shared across all cards.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All three building blocks ready for Plan 02 composition into the full InsightsPage
- SECTION_CONFIG and getInsightsForCategory ready for tab rendering in the page assembler
- GenerateButton and InsightCard are drop-in components with clean interfaces

---
*Phase: 05-insights*
*Completed: 2026-03-02*

## Self-Check: PASSED

- FOUND: web-app/src/lib/insights-helpers.ts
- FOUND: web-app/src/components/insights/generate-button.tsx
- FOUND: web-app/src/components/insights/insight-card.tsx
- FOUND: .planning/phases/05-insights/05-01-SUMMARY.md
- COMMIT 06d17d5: feat(05-01): create insights-helpers.ts
- COMMIT b8ae699: feat(05-01): create GenerateButton component
- COMMIT ec64adc: feat(05-01): create InsightCard component
