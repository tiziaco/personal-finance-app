---
phase: 07-polish
plan: "01"
subsystem: ui
tags: [tailwind, css-variables, oklch, dark-mode, design-tokens]

# Dependency graph
requires:
  - phase: 06-budgets-settings
    provides: Settings page with data-section and server-status components
  - phase: 04-analytics
    provides: income-vs-expenses-tab and trends-tab components
  - phase: 03-transactions
    provides: transactions-table component with confidence score column
provides:
  - --success and --warning CSS variable tokens in globals.css (light + dark OKLCH values)
  - text-success and text-warning Tailwind utility classes via @theme inline
  - Dark-mode-safe semantic color tokens across all affected components
affects: [any future component using positive financial values or warning indicators]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "OKLCH CSS custom properties in :root and .dark for semantic color meaning"
    - "@theme inline exposes CSS variables as Tailwind utility classes"
    - "text-success / text-warning instead of text-green-600 / text-amber-600 for semantic color"
    - "text-destructive / border-destructive instead of text-red-500 / border-red-500"
    - "dark:bg-{color}-400 companions added alongside bg-{color}-500 for dark-mode visibility"

key-files:
  created: []
  modified:
    - web-app/src/styles/globals.css
    - web-app/src/components/analytics/income-vs-expenses-tab.tsx
    - web-app/src/components/analytics/trends-tab.tsx
    - web-app/src/components/transactions/transactions-table.tsx
    - web-app/src/components/settings/sections/data-section.tsx
    - web-app/src/components/settings/server-status.tsx

key-decisions:
  - "OKLCH values used bare (no hsl() wrapper) — consistent with prior STATE.md decision; hsl() breaks color rendering in Tailwind v4"
  - "--success light: oklch(0.55 0.15 145), dark: oklch(0.70 0.15 145) — darker light-mode for legibility, brighter dark-mode"
  - "--warning light: oklch(0.72 0.15 65), dark: oklch(0.82 0.15 65) — same pattern for amber-family warning hue"
  - "server-status.tsx statusColor variable updated to include dark: companions — avoids creating separate dark: class strings per element"
  - "hover:bg-destructive/10 used instead of hover:bg-red-50 — semantic token with opacity modifier, adapts to dark backgrounds"

patterns-established:
  - "Semantic color tokens: define in :root and .dark with OKLCH values, expose via @theme inline, use as Tailwind utility classes"
  - "Dark-mode dot indicators: always pair bg-{color}-500 with dark:bg-{color}-400 for visibility on dark backgrounds"

requirements-completed: [DESGN-01, DESGN-02]

# Metrics
duration: 1min
completed: 2026-03-03
---

# Phase 7 Plan 1: Semantic Color Tokens for Dark Mode Summary

**OKLCH --success and --warning CSS tokens added to globals.css, replacing text-green-600/text-amber-600/border-red-500 raw classes across 5 components with dark-mode-adaptive semantic tokens.**

## Performance

- **Duration:** ~1 min
- **Started:** 2026-03-03T09:32:15Z
- **Completed:** 2026-03-03T09:33:32Z
- **Tasks:** 2
- **Files modified:** 6

## Accomplishments

- Defined --success and --warning CSS custom properties in both :root (light) and .dark using bare OKLCH values, exposed via @theme inline as text-success and text-warning Tailwind classes
- Replaced all text-green-600 occurrences in income-vs-expenses-tab.tsx (4 occurrences) and trends-tab.tsx (1 occurrence) with text-success
- Replaced text-amber-600/text-green-600 confidence score colors in transactions-table.tsx with text-warning/text-success
- Replaced border-red-500/text-red-500/hover:bg-red-50 in data-section.tsx (2 buttons) with border-destructive/text-destructive/hover:bg-destructive/10
- Added dark:bg-green-400 and dark:bg-red-400 dark-mode companions to all bg-green-500 and bg-red-500 status dot classes in server-status.tsx

## Task Commits

Each task was committed atomically:

1. **Task 1: Add --success and --warning CSS variable tokens to globals.css** - `1e15c90` (feat)
2. **Task 2: Replace raw color classes with semantic tokens across 5 components** - `bb4c567` (feat)

## Files Created/Modified

- `web-app/src/styles/globals.css` - Added --color-success/--color-warning to @theme inline; --success/--warning to :root and .dark with OKLCH values
- `web-app/src/components/analytics/income-vs-expenses-tab.tsx` - 4x text-green-600 → text-success
- `web-app/src/components/analytics/trends-tab.tsx` - 1x text-green-600 → text-success
- `web-app/src/components/transactions/transactions-table.tsx` - text-amber-600/text-green-600 → text-warning/text-success on confidence score
- `web-app/src/components/settings/sections/data-section.tsx` - 2x border-red-500/text-red-500/hover:bg-red-50 → border-destructive/text-destructive/hover:bg-destructive/10
- `web-app/src/components/settings/server-status.tsx` - statusColor variable updated; all HoverCard component dots updated with dark: companions

## Decisions Made

- OKLCH values used bare (no hsl() wrapper) — consistent with prior STATE.md decision; hsl() wrapper breaks color rendering in Tailwind v4
- --success light-mode value set lower (0.55 L) for legibility on white backgrounds; dark-mode higher (0.70 L) for brightness on dark
- hover:bg-destructive/10 used instead of hover:bg-red-50 — opacity modifier pattern adapts automatically in dark mode without extra dark: variant
- server-status.tsx statusColor variable approach: updated the variable's string values to include dark: companions rather than per-element inline variants — minimal diff, correct behavior

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- text-success and text-warning are now available globally as Tailwind classes via CSS token infrastructure
- All five target component files have zero remaining text-green-600, text-amber-600, border-red-500, or hover:bg-red-50 occurrences
- TypeScript passes with no errors (npx tsc --noEmit confirmed)
- Phase 07 Plan 02 (dark mode layout / theme toggle) can proceed — DESGN-01 and DESGN-02 color token requirements satisfied

## Self-Check: PASSED

- All 6 modified files exist on disk
- Both task commits found in git log (1e15c90, bb4c567)
- SUMMARY.md created at expected path
- TypeScript check: npx tsc --noEmit passes with zero errors

---
*Phase: 07-polish*
*Completed: 2026-03-03*
