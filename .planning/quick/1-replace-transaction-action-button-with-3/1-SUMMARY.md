---
phase: quick
plan: 1
subsystem: transactions
tags: [ux, delete, dropdown-menu, hooks]
dependency_graph:
  requires: []
  provides: [useDeleteTransaction, per-transaction-delete]
  affects: [transactions-table, transactions-page]
tech_stack:
  added: []
  patterns: [3-dot DropdownMenu row actions, single-item batch delete]
key_files:
  created: []
  modified:
    - web-app/src/hooks/use-transaction-mutations.ts
    - web-app/src/components/transactions/transactions-table.tsx
    - web-app/src/app/(app)/transactions/page.tsx
decisions:
  - "DropdownMenuTrigger used without asChild — base-ui MenuPrimitive.Trigger does not support asChild; trigger styled directly via className prop"
  - "Delete uses batchDeleteTransactions with single-item array — reuses existing API function signature (BatchDeleteRequest = { ids: number[] }) instead of adding a new endpoint"
  - "DropdownMenuItem delete styled via className text-destructive — DropdownMenuItem variant='destructive' also exists but inline className matches the plan spec"
metrics:
  duration: ~5 minutes
  completed_date: "2026-03-11T08:33:41Z"
  tasks_completed: 3
  files_modified: 3
---

# Quick Task 1: Replace Transaction Action Button with 3-dot Menu — Summary

**One-liner:** Per-transaction 3-dot DropdownMenu with Edit and Delete actions, wired to batchDeleteTransactions API via new useDeleteTransaction hook.

## What Was Built

Replaced the single Edit pencil button in the transaction table (desktop Actions column) and mobile TransactionCard with a 3-dot `DropdownMenu` exposing two actions: Edit (existing behaviour) and Delete (new). Delete is styled with `text-destructive` and calls a new `useDeleteTransaction` hook that wraps `batchDeleteTransactions` with a single-item array.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Add useDeleteTransaction hook | d39181a | use-transaction-mutations.ts |
| 2 | Replace Edit button with 3-dot DropdownMenu | 012b25d | transactions-table.tsx |
| 3 | Wire onDeleteTransaction in TransactionsPage | d7a6f1c | page.tsx |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] DropdownMenuTrigger does not support asChild**
- **Found during:** Task 2
- **Issue:** The plan specified `<DropdownMenuTrigger asChild>` wrapping a `<button>` or `<Button>`, but the project's `dropdown-menu.tsx` is built on `@base-ui/react/menu` (`MenuPrimitive.Trigger`) which has no `asChild` prop — TypeScript error TS2322.
- **Fix:** Removed `asChild` and applied button styling (`className`, `aria-label`) directly on `DropdownMenuTrigger`. The trigger renders as a `<button>` natively, so no wrapper element is needed.
- **Files modified:** `web-app/src/components/transactions/transactions-table.tsx`
- **Commit:** 012b25d

## Self-Check: PASSED

- [x] `web-app/src/hooks/use-transaction-mutations.ts` — useDeleteTransaction exported
- [x] `web-app/src/components/transactions/transactions-table.tsx` — DropdownMenu in desktop and mobile
- [x] `web-app/src/app/(app)/transactions/page.tsx` — onDeleteTransaction wired
- [x] `npx tsc --noEmit` passes with no errors
- [x] Commits d39181a, 012b25d, d7a6f1c verified in git log
