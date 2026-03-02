---
phase: 06-budgets-settings
plan: "03"
subsystem: ui
tags: [react, tanstack-query, alert-dialog, settings, transactions]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: fetchTransactions, batchDeleteTransactions API functions and transaction types
  - phase: 03-transactions
    provides: transaction data model and batch delete API contracts
provides:
  - useDeleteAllTransactions mutation hook with pagination + batch deletion
  - DataSection with Transactions AlertDialog (Delete All Transactions)
  - NotificationsSection with three Coming Soon badge placeholders
  - Settings dialog with Notifications nav replacing Integrations
affects: []

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Paginate-then-batch-delete: fetch all IDs in pages of 100, delete in chunks of 100
    - AlertDialog confirm pattern: AlertDialogTrigger render prop, AlertDialogAction with disabled+pending text

key-files:
  created:
    - web-app/src/hooks/use-delete-all-transactions.ts
    - web-app/src/components/settings/sections/notifications-section.tsx
  modified:
    - web-app/src/components/settings/sections/data-section.tsx
    - web-app/src/components/settings/settings-dialog.tsx
  deleted:
    - web-app/src/components/settings/sections/integrations-section.tsx

key-decisions:
  - "useDeleteAllTransactions paginates with limit=100 breaking when items.length < pageSize — matches backend BatchDeleteRequest 100-ID cap"
  - "NotificationsSection uses Badge variant=secondary (Coming Soon) instead of Switch — non-functional placeholders, no false affordance"
  - "Integrations section deleted entirely — Google Drive/Slack template leftover with no relevance to personal finance app"

patterns-established:
  - "Paginate-then-batch-delete: collect all IDs in while loop with offset, delete in for loop with i += pageSize"
  - "AlertDialogTrigger render prop pattern for base-ui AlertDialog with Button trigger"

requirements-completed: [SETT-04, SETT-05]

# Metrics
duration: 2min
completed: 2026-03-02
---

# Phase 6 Plan 03: Settings Data Management and Notifications Summary

**Delete All Transactions AlertDialog with pagination-safe mutation hook, and Coming Soon Notifications section replacing template Integrations nav**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-02T16:53:22Z
- **Completed:** 2026-03-02T16:54:39Z
- **Tasks:** 2
- **Files modified:** 5 (2 created, 2 modified, 1 deleted)

## Accomplishments
- Created `useDeleteAllTransactions` hook that safely handles large datasets by paginating fetch (limit=100) then deleting in 100-ID batches — matches backend API constraints
- Added "Transactions" SettingSection to DataSection with AlertDialog: shows "Delete all transactions?" confirmation, "Deleting…" pending state, destructive action button
- Created NotificationsSection with three Coming Soon badge placeholders (Email Alerts, Budget Alerts, Newsletter) — non-functional by design, no false affordance
- Updated settings-dialog.tsx: replaced Integrations nav with Notifications (Bell icon), deleted irrelevant integrations-section.tsx template file

## Task Commits

1. **Task 1: Create useDeleteAllTransactions hook** - `739624d` (feat)
2. **Task 2: Update DataSection, create NotificationsSection, clean up settings dialog** - `1b9b64d` (feat)

## Files Created/Modified
- `web-app/src/hooks/use-delete-all-transactions.ts` - Mutation hook: paginate all IDs, batch delete in 100s, invalidate 4 query caches, success/error toasts
- `web-app/src/components/settings/sections/data-section.tsx` - Added Transactions SettingSection with AlertDialog; preserved Data Management and Storage sections
- `web-app/src/components/settings/sections/notifications-section.tsx` - New section with Email Alerts, Budget Alerts, Newsletter — each with Coming Soon badge
- `web-app/src/components/settings/settings-dialog.tsx` - Type changed to `"general" | "notifications" | "data"`, Bell icon, NotificationsSection case, Integrations removed
- `web-app/src/components/settings/sections/integrations-section.tsx` - DELETED (template leftover)

## AlertDialog Copy
- **Title:** "Delete all transactions?"
- **Description:** "This will permanently remove all your transaction history. This action cannot be undone."
- **Cancel label:** "Cancel"
- **Action label (idle):** "Delete all"
- **Action label (pending):** "Deleting…"

## Notification Items
| ID | Label | Description |
|----|-------|-------------|
| email | Email Alerts | Receive weekly spending summaries by email |
| budget | Budget Alerts | Get notified when you approach a budget limit |
| newsletter | Newsletter | Tips and updates about new features |

## Decisions Made
- `useDeleteAllTransactions` paginates with `limit=100`, breaks when `page.items.length < pageSize` — matches backend's 100-ID cap on `BatchDeleteRequest`
- `NotificationsSection` uses `Badge variant="secondary"` (Coming Soon) instead of Switch components — non-functional placeholders should not show false affordance
- `integrations-section.tsx` deleted entirely — Google Drive and Slack integrations are template leftovers with no relevance to a personal finance app

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- SETT-04 and SETT-05 requirements satisfied
- Settings dialog is clean: General, Notifications, Data sections
- Delete All Transactions flow is production-ready with pagination safety
- No blockers for remaining Phase 06 plans

---
*Phase: 06-budgets-settings*
*Completed: 2026-03-02*
