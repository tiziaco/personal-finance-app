---
phase: 07-polish
plan: "04"
subsystem: transactions-ui
tags: [mobile, responsive, card-list, pagination, tailwind]
dependency_graph:
  requires: [07-02, 07-03]
  provides: [DESGN-06]
  affects: [web-app/src/components/transactions/transactions-table.tsx]
tech_stack:
  added: []
  patterns:
    - "Dual-render: hidden sm:block table + sm:hidden card-list at Tailwind sm breakpoint (640px)"
    - "Local non-exported TransactionCard component calling hooks directly (React hooks rules compliant)"
    - "Pagination extracted outside both wrappers so it renders at all breakpoints"
key_files:
  created: []
  modified:
    - web-app/src/components/transactions/transactions-table.tsx
decisions:
  - "useCurrency().formatAmount used in TransactionCard (local function component can call hooks directly); useFormatCurrency shadow-import used in parent component for desktop column defs — no hook rule violations"
  - "Pagination div extracted outside the rounded-lg border wrapper — was previously inside the table border; extraction ensures it is visible on mobile where the table wrapper is hidden"
  - "TransactionCard does not include a checkbox — bulk actions remain desktop-only for v1; card-list is read/edit only on mobile"
metrics:
  duration: "checkpoint continuation — task 1 only"
  completed_date: "2026-03-03"
  tasks_completed: 2
  files_modified: 1
---

# Phase 7 Plan 04: Mobile Card-List for TransactionsTable Summary

Dual-render TransactionsTable with `hidden sm:block` desktop table and `sm:hidden` card-list on mobile, plus pagination extracted outside both wrappers so it is visible at all breakpoints.

## What Was Built

The `TransactionsTable` component now renders two separate layouts controlled by Tailwind breakpoint classes:

- **Desktop (>=640px):** The existing `<table>` with all 7 columns (select, date, merchant, amount, category, confidence, actions) wrapped in `hidden sm:block`. No change to desktop appearance.
- **Mobile (<640px):** A `sm:hidden` card-list where each transaction is a `TransactionCard` showing merchant name, formatted date, category badge, formatted amount, and an edit button with `min-h-12 min-w-12` (>=48px tap target).
- **Pagination:** Extracted from inside the `rounded-lg border` wrapper to a standalone block outside both the table and the card-list, ensuring Previous/Next controls are always visible regardless of breakpoint.

A local non-exported `TransactionCard` function component was added above `TransactionsTable`. It calls `useFormatDate()` and `useCurrency().formatAmount` directly (both are valid hook calls in a function component). The parent component continues to use `useFormatCurrency()` for the desktop Amount column cell renderer.

## Tasks Completed

| Task | Description | Commit | Files |
|------|-------------|--------|-------|
| 1 | Implement mobile card-list and extract pagination outside table wrapper | 69f559f | web-app/src/components/transactions/transactions-table.tsx |
| 2 | Human verify — checkpoint approved | n/a | — |

## Deviations from Plan

None — plan executed exactly as written.

## Verification

- `hidden sm:block` applied to desktop table wrapper: confirmed in file (line 202)
- `sm:hidden` applied to mobile card-list wrapper: confirmed in file (line 242)
- Pagination div is outside both `.rounded-lg.border` and `.sm:hidden` wrappers: confirmed at line 257
- TypeScript compiled without errors (verified during task 1)
- Human checkpoint approved: mobile card-list renders correctly at 375px, edit buttons have adequate tap target, pagination works, desktop table unchanged

## Self-Check: PASSED

- File exists: `web-app/src/components/transactions/transactions-table.tsx` — FOUND
- Commit 69f559f exists in git log — FOUND
