# Transaction Full Edit — Design Spec

**Date:** 2026-03-16
**Branch:** improve-transaction-management

## Problem

The "Edit" dropdown action on a transaction currently opens `CategoryEditModal`, which only lets the user change the category. The backend `TransactionUpdate` schema already supports all user-editable fields. The frontend needs to expose them.

## Scope

- **Single transaction edit**: expand to all user-editable fields (date, merchant, amount, category, description, is_recurring)
- **Bulk edit**: unchanged — category-only recategorization is intentional and matches industry standard (Mint, YNAB, Monarch Money, Copilot)
- **Category badge quick-edit**: unchanged — clicking the category badge in the table still opens `CategoryEditModal`

## Design

### 1. Types — `types/transaction.ts`

Add a new `TransactionUpdateRequest` interface:

```ts
interface TransactionUpdateRequest {
  date?: string           // ISO 8601 date string
  merchant?: string
  amount?: string         // Decimal as string, e.g. '-42.50'
  description?: string
  category?: CategoryEnum
  is_recurring?: boolean
}
```

All fields are optional (PATCH semantics). `original_category` and `confidence_score` are deliberately excluded — they are system-managed and not user-editable.

### 2. API client — `lib/api/transactions.ts`

Widen the `data` parameter of `updateTransaction` from `Partial<Pick<TransactionResponse, 'category'>>` to `TransactionUpdateRequest`.

### 3. Mutation — `hooks/use-transaction-mutations.ts`

Update `useUpdateTransaction`:

- Payload type changes to `{ id: number } & TransactionUpdateRequest`
- Add optimistic update: cancel in-flight `['transactions']` queries, snapshot all cached pages, find the transaction by ID across all pages and replace it with the new field values, rollback on error, invalidate on settled
- Toast message: "Transaction updated" (was "Category updated")

### 4. New component — `components/transactions/edit-transaction-dialog.tsx`

A new `EditTransactionDialog` component, separate from `AddTransactionDialog`.

**Props:**
```ts
interface EditTransactionDialogProps {
  transaction: TransactionResponse | null
  open: boolean
  onOpenChange: (open: boolean) => void
}
```

**Behaviour:**
- Pre-populates form state from `transaction` when it opens (reset on close)
- Fields: date (calendar picker), merchant (text input), amount (number input), category (select), description (text input, optional), is_recurring (checkbox)
- On submit, diffs the form state against the original transaction and sends only changed fields in the PATCH — avoids unnecessary updates
- Title: "Edit Transaction", submit button: "Save Changes"
- Validation: date, merchant, and a finite amount are required; category is required

### 5. Wiring — `app/(app)/transactions/page.tsx`

- Rename `editingTransaction` → `editingCategory` (controls `CategoryEditModal`, unchanged)
- Add `editingTransactionFull: TransactionResponse | null` state (controls `EditTransactionDialog`)
- In `TransactionsTable`, rename prop `onEditTransaction` → `onEditCategory` (badge click → `CategoryEditModal`) and add `onEditTransaction` (dropdown "Edit" item → `EditTransactionDialog`)
- Render `<EditTransactionDialog>` alongside the existing modals

### 6. Table — `components/transactions/transactions-table.tsx`

- Rename `onEditTransaction` prop to `onEditCategory`
- Add `onEditTransaction` prop
- Category badge `onClick` calls `onEditCategory`
- Dropdown "Edit" item `onClick` calls `onEditTransaction`
- Same change applied to `TransactionCard` (mobile view)

## What is NOT changing

- `CategoryEditModal` — untouched
- `AddTransactionDialog` — untouched
- Bulk recategorize flow — category-only, untouched
- Backend — already supports all fields; no changes needed

## Files changed

| File | Change |
|------|--------|
| `web-app/src/types/transaction.ts` | Add `TransactionUpdateRequest` |
| `web-app/src/lib/api/transactions.ts` | Widen `updateTransaction` param type |
| `web-app/src/hooks/use-transaction-mutations.ts` | Expand `useUpdateTransaction` payload + optimistic update |
| `web-app/src/components/transactions/edit-transaction-dialog.tsx` | New file |
| `web-app/src/components/transactions/transactions-table.tsx` | Rename prop, add new prop |
| `web-app/src/app/(app)/transactions/page.tsx` | Wire up new dialog and renamed props |
