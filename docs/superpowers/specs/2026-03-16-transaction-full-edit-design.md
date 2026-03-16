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
  amount?: string         // CRITICAL: Decimal as string — e.g. '-42.50' for expense, '1200.00' for income; must NOT be number
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
- Add optimistic update following the same `onMutate` / `onError` / `onSettled` structure as `useCreateTransaction` (use it as the reference implementation): call `cancelQueries` first to prevent race conditions, snapshot all pages via `getQueriesData({ queryKey: ['transactions'] })`, update the matching transaction by ID in `setQueriesData` by spreading the existing item and overwriting only the changed keys (`{ ...existingItem, ...changedFields }`), rollback all snapshots in `onError`, invalidate on `onSettled`
- Success toast: "Transaction updated"; error toast: "Failed to update transaction"

**Important:** `CategoryEditModal` currently calls `useUpdateTransaction` with `{ id, category }`. After this change the call remains type-valid, but the toast message will change to "Transaction updated". To preserve the correct "Category updated" message for the quick-edit flow, extract a dedicated `useUpdateTransactionCategory` hook (narrow payload: `{ id: number; category: CategoryEnum }`, toast: "Category updated") and keep `CategoryEditModal` wired to that. `useUpdateTransaction` becomes the full-edit mutation used only by `EditTransactionDialog`.

**Amount diffing:** When computing which fields changed, compare `amount` numerically via `parseFloat` rather than by string equality (e.g. `"-42.5"` and `"-42.50"` are the same value). Only include `amount` in the PATCH payload if `parseFloat(newAmount) !== parseFloat(originalAmount)`.

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
- Pre-populates form state from `transaction` when it opens; uses a `useEffect` keyed on `transaction?.id` to reset form fields whenever a different transaction is passed
- On close (`onOpenChange(false)`), form resets to empty so re-opening a different transaction does not flash previous values
- Fields: date (calendar picker), merchant (text input), amount (number input), category (select), description (text input, optional), is_recurring (checkbox)
- On submit, diffs the form state against the original transaction and sends only changed fields in the PATCH — avoids unnecessary updates. Amount is diffed numerically via `parseFloat` (see Section 3). If the diff produces an empty object (nothing changed), the "Save Changes" button is disabled — do not fire a no-op PATCH.
- **`description` null handling:** initialise the description input as `transaction.description ?? ''`. The backend service uses `model_dump(exclude_none=True)`, which means sending `description: null` is silently ignored and does NOT clear the DB value. Therefore, treat an empty description input as "do not send this field" — omit `description` from the PATCH payload entirely when the trimmed value is `''`, consistent with how `AddTransactionDialog` handles it today (`description: form.description.trim() || undefined`). Consequence: description can be set to a non-empty value but cannot be cleared back to null through this dialog without a backend change (out of scope).
- Title: "Edit Transaction", submit button: "Save Changes" (disabled when no fields have changed)
- Validation: date, merchant, and a finite amount are required; category is required
- On successful save, close the dialog by passing `onSuccess: () => onOpenChange(false)` as a per-call callback to `mutate(...)` — consistent with how `CategoryEditModal` closes itself today

### 5. Wiring — `app/(app)/transactions/page.tsx`

- Rename the **existing** `editingTransaction` state variable → `editingCategory` (and `setEditingTransaction` → `setEditingCategory`), freeing the name for the new full-edit state. Update all three JSX references in the `CategoryEditModal` block: `transaction={editingCategory}`, `open={editingCategory !== null}`, and `onOpenChange={(open) => { if (!open) setEditingCategory(null) }}`.
- Add new `editingTransaction: TransactionResponse | null` state (controls `EditTransactionDialog`)
- In `TransactionsTable`, rename the **existing** `onEditTransaction` prop → `onEditCategory` (category badge click → `CategoryEditModal`) and add a new `onEditTransaction` prop (dropdown "Edit" item → `EditTransactionDialog`)
- Render `<EditTransactionDialog>` alongside the existing modals

### 6. Table — `components/transactions/transactions-table.tsx`

- Rename `onEditTransaction` prop to `onEditCategory`; add `onEditTransaction` prop
- **Category badge `onClick` (column 5, currently line 172):** change from `onEditTransaction` to `onEditCategory` — this is the one internal call site that must change
- **Dropdown "Edit" `onClick` (column 7, currently line 202):** keeps `onEditTransaction` — no change needed here; after `page.tsx` passes the full-edit callback as `onEditTransaction`, this wiring is already correct

**`TransactionCard` (mobile view):** The mobile card's category display is a plain non-interactive `<span>` with no `onClick`, so there is no badge-click path to wire. Rename its internal `onEdit` prop to `onEditTransaction`. The instantiation inside `TransactionsTable` (currently `onEdit={onEditTransaction}`) must change to `onEditTransaction={onEditTransaction}` — both the prop name on the element and the value being passed change simultaneously. `onEditCategory` is intentionally not forwarded to `TransactionCard`.

## What is NOT changing

- `CategoryEditModal` — logic and UI untouched; only its hook import changes (see Section 3)
- `AddTransactionDialog` — untouched
- Bulk recategorize flow — category-only, untouched
- Backend — already supports all fields; no changes needed

## Files changed

| File | Change |
|------|--------|
| `web-app/src/types/transaction.ts` | Add `TransactionUpdateRequest` |
| `web-app/src/lib/api/transactions.ts` | Widen `updateTransaction` param type |
| `web-app/src/hooks/use-transaction-mutations.ts` | Expand `useUpdateTransaction` payload + optimistic update; extract `useUpdateTransactionCategory` for `CategoryEditModal` |
| `web-app/src/components/transactions/edit-transaction-dialog.tsx` | New file |
| `web-app/src/components/transactions/category-edit-modal.tsx` | Swap `useUpdateTransaction` import to `useUpdateTransactionCategory` |
| `web-app/src/components/transactions/transactions-table.tsx` | Rename prop, add new prop; rename `TransactionCard` internal `onEdit` → `onEditTransaction` |
| `web-app/src/app/(app)/transactions/page.tsx` | Wire up new dialog and renamed props |
