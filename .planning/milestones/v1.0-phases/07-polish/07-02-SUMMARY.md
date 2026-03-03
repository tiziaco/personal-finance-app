---
phase: 07-polish
plan: 02
subsystem: ui
tags: [react, context, localStorage, currency, intl, nextjs]

# Dependency graph
requires:
  - phase: 06-budgets-settings
    provides: DateFormatProvider pattern (localStorage, SSR-safe useEffect, shadow-import hook)
provides:
  - CurrencyProvider context with EUR/USD/GBP/CHF support and formatAmount function
  - useFormatCurrency shadow-import hook for drop-in replacement at call sites
  - Currency dropdown in Settings GeneralSection (Regional section)
  - All monetary display components now respect user currency preference reactively
affects: [07-03, 07-04, 07-05]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "CurrencyProvider mirrors DateFormatProvider pattern exactly (localStorage read post-mount, SSR-safe)"
    - "Shadow-import hook (useFormatCurrency) enables zero-JSX-change call site migration"
    - "LOCALE_MAP maps Currency -> Intl locale string for correct number formatting per region"

key-files:
  created:
    - web-app/src/providers/currency-provider.tsx
    - web-app/src/hooks/use-currency-format.ts
  modified:
    - web-app/src/app/layout.tsx
    - web-app/src/components/settings/sections/general-section.tsx
    - web-app/src/components/dashboard/welcome-card.tsx
    - web-app/src/components/dashboard/summary-cards.tsx
    - web-app/src/components/dashboard/recent-transactions.tsx
    - web-app/src/components/transactions/category-edit-modal.tsx
    - web-app/src/components/transactions/transactions-table.tsx
    - web-app/src/components/analytics/spending-by-category-tab.tsx
    - web-app/src/components/analytics/trends-tab.tsx
    - web-app/src/components/analytics/income-vs-expenses-tab.tsx

key-decisions:
  - "LOCALE_MAP ties Currency to Intl locale (EUR->de-DE, USD->en-US, GBP->en-GB, CHF->de-CH) for culturally correct formatting"
  - "CurrencyProvider placed inside DateFormatProvider but outside QueryProvider — consistent nesting with existing provider chain"
  - "insights-helpers.ts left unmigrated — pure utility file, no React context, formats for static AI-generated strings not interactive UI"

patterns-established:
  - "Shadow-import pattern: const formatCurrency = useFormatCurrency() at component top replaces static import with zero JSX changes"

requirements-completed: [SETT-01]

# Metrics
duration: 3min
completed: 2026-03-03
---

# Phase 7 Plan 02: Currency Preference Setting Summary

**CurrencyProvider context with EUR/USD/GBP/CHF support wired into layout and 8 call-site migrations so all monetary amounts update reactively when user changes currency in Settings**

## Performance

- **Duration:** ~3 min
- **Started:** 2026-03-03T09:06:51Z
- **Completed:** 2026-03-03T09:09:18Z
- **Tasks:** 3
- **Files modified:** 10

## Accomplishments
- Built CurrencyProvider mirroring DateFormatProvider exactly: localStorage persistence, SSR-safe useEffect hydration, formatAmount with Intl.NumberFormat per currency/locale
- Added Currency dropdown to Settings Regional section with EUR/USD/GBP/CHF options including locale example strings
- Migrated all 8 component call sites from static `formatCurrency` import to `useFormatCurrency()` hook with zero JSX changes at use points

## Task Commits

Each task was committed atomically:

1. **Task 1: Create CurrencyProvider and useFormatCurrency hook** - `e7ebeb4` (feat)
2. **Task 2: Wire CurrencyProvider into root layout and add currency dropdown to Settings** - `368ae3d` (feat)
3. **Task 3: Migrate all formatCurrency call sites to useFormatCurrency hook** - `b1c98db` (feat)

## Files Created/Modified
- `web-app/src/providers/currency-provider.tsx` - CurrencyProvider context; exports CurrencyProvider, useCurrency, Currency type; LOCALE_MAP for Intl formatting
- `web-app/src/hooks/use-currency-format.ts` - Shadow-import hook returning bound formatAmount from CurrencyProvider
- `web-app/src/app/layout.tsx` - Added CurrencyProvider import and wrapper inside DateFormatProvider
- `web-app/src/components/settings/sections/general-section.tsx` - Currency dropdown in Regional section; CURRENCY_OPTIONS with examples
- `web-app/src/components/dashboard/welcome-card.tsx` - Migrated to useFormatCurrency hook
- `web-app/src/components/dashboard/summary-cards.tsx` - Migrated to useFormatCurrency hook (4 calls)
- `web-app/src/components/dashboard/recent-transactions.tsx` - Migrated to useFormatCurrency hook
- `web-app/src/components/transactions/category-edit-modal.tsx` - Migrated to useFormatCurrency hook
- `web-app/src/components/transactions/transactions-table.tsx` - Migrated to useFormatCurrency hook (column accessor cell)
- `web-app/src/components/analytics/spending-by-category-tab.tsx` - Migrated to useFormatCurrency hook; kept formatPercent from lib/format
- `web-app/src/components/analytics/trends-tab.tsx` - Migrated to useFormatCurrency hook
- `web-app/src/components/analytics/income-vs-expenses-tab.tsx` - Migrated to useFormatCurrency hook (5 calls)

## Decisions Made
- LOCALE_MAP ties each Currency to its natural Intl locale (EUR->de-DE, USD->en-US, GBP->en-GB, CHF->de-CH) for culturally correct number formatting
- CurrencyProvider placed inside DateFormatProvider and outside QueryProvider, consistent with the existing provider chain pattern
- insights-helpers.ts left unmigrated as it is a pure utility file with no React context, used for static AI-generated display strings

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SETT-01 fully resolved: currency preference persists in localStorage and all monetary displays update reactively
- Remaining Phase 7 plans (07-03 already complete, 07-04, 07-05) can proceed independently
- No blockers

---
*Phase: 07-polish*
*Completed: 2026-03-03*

## Self-Check: PASSED
- currency-provider.tsx: FOUND
- use-currency-format.ts: FOUND
- 07-02-SUMMARY.md: FOUND
- Commit e7ebeb4: FOUND
- Commit 368ae3d: FOUND
- Commit b1c98db: FOUND
