# Transaction Full Edit — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand single-transaction editing from category-only to all user-editable fields (date, merchant, amount, category, description, is_recurring) while keeping bulk edit and the category-badge quick-edit unchanged.

**Architecture:** Add a `TransactionUpdateRequest` type and widen the API client; extract a narrow `useUpdateTransactionCategory` hook for `CategoryEditModal` and expand `useUpdateTransaction` with optimistic updates for the new `EditTransactionDialog`; rename the table's `onEditTransaction` prop to `onEditCategory` and add a new `onEditTransaction` for the full-edit path; wire everything in `TransactionsPage`.

**Tech Stack:** Next.js 15 (App Router), React, TypeScript, TanStack Query v5, Tailwind CSS, shadcn/ui, date-fns

**Spec:** `docs/superpowers/specs/2026-03-16-transaction-full-edit-design.md`

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `web-app/src/types/transaction.ts` | Modify | Add `TransactionUpdateRequest` interface |
| `web-app/src/lib/api/transactions.ts` | Modify | Widen `updateTransaction` param type |
| `web-app/src/hooks/use-transaction-mutations.ts` | Modify | Extract `useUpdateTransactionCategory`; expand `useUpdateTransaction` with full payload + optimistic update |
| `web-app/src/components/transactions/category-edit-modal.tsx` | Modify | Swap hook import from `useUpdateTransaction` → `useUpdateTransactionCategory` |
| `web-app/src/components/transactions/edit-transaction-dialog.tsx` | Create | New dialog for full single-transaction editing |
| `web-app/src/components/transactions/transactions-table.tsx` | Modify | Rename `onEditTransaction` → `onEditCategory`, add `onEditTransaction`, update call sites and `TransactionCard` |
| `web-app/src/app/(app)/transactions/page.tsx` | Modify | Rename state, wire `EditTransactionDialog` |

---

## Chunk 1: Foundation

### Task 1: Add `TransactionUpdateRequest` type

**Files:**
- Modify: `web-app/src/types/transaction.ts`

- [ ] **Step 1: Add the interface after `CreateTransactionRequest`**

Open `web-app/src/types/transaction.ts`. After the `CreateTransactionRequest` interface (currently the last export, around line 109), add:

```ts
export interface TransactionUpdateRequest {
  date?: string
  merchant?: string
  /** CRITICAL: Decimal as string — e.g. '-42.50' for expense, '1200.00' for income; must NOT be number */
  amount?: string
  /** null not supported for clearing — backend uses exclude_none=True */
  description?: string
  category?: CategoryEnum
  is_recurring?: boolean
}
```

- [ ] **Step 2: Verify TypeScript accepts the new type**

```bash
cd web-app && npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors (or only pre-existing errors unrelated to this file).

- [ ] **Step 3: Commit**

```bash
git add web-app/src/types/transaction.ts
git commit -m "feat: add TransactionUpdateRequest type"
```

---

### Task 2: Widen `updateTransaction` API function

**Files:**
- Modify: `web-app/src/lib/api/transactions.ts`

- [ ] **Step 1: Add `TransactionUpdateRequest` to the import**

At the top of `web-app/src/lib/api/transactions.ts`, the existing import block reads:

```ts
import type {
  TransactionListResponse,
  TransactionResponse,
  TransactionFilters,
  BatchUpdateRequest,
  BatchUpdateResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
  CreateTransactionRequest,
} from '@/types/transaction'
```

Add `TransactionUpdateRequest` to the list:

```ts
import type {
  TransactionListResponse,
  TransactionResponse,
  TransactionFilters,
  BatchUpdateRequest,
  BatchUpdateResponse,
  BatchDeleteRequest,
  BatchDeleteResponse,
  CreateTransactionRequest,
  TransactionUpdateRequest,
} from '@/types/transaction'
```

- [ ] **Step 2: Widen the `updateTransaction` function signature**

Find the `updateTransaction` function (currently lines 65–74):

```ts
export async function updateTransaction(
  token: string | null,
  id: number,
  data: Partial<Pick<TransactionResponse, 'category'>>
): Promise<TransactionResponse> {
```

Replace the `data` parameter type:

```ts
export async function updateTransaction(
  token: string | null,
  id: number,
  data: TransactionUpdateRequest
): Promise<TransactionResponse> {
```

The function body is unchanged — it already passes `data` through `JSON.stringify`.

- [ ] **Step 3: Verify no TypeScript errors**

```bash
cd web-app && npx tsc --noEmit 2>&1 | head -20
```

Expected: no new errors.

- [ ] **Step 4: Commit**

```bash
git add web-app/src/lib/api/transactions.ts
git commit -m "feat: widen updateTransaction API param to TransactionUpdateRequest"
```

---

### Task 3: Extract narrow hook and expand `useUpdateTransaction`

**Files:**
- Modify: `web-app/src/hooks/use-transaction-mutations.ts`

- [ ] **Step 1: Add `TransactionUpdateRequest` to the import**

At the top of `use-transaction-mutations.ts`, the existing import reads:

```ts
import type { CategoryEnum, CreateTransactionRequest, TransactionListResponse, TransactionResponse } from '@/types/transaction'
```

Add `TransactionUpdateRequest`:

```ts
import type { CategoryEnum, CreateTransactionRequest, TransactionListResponse, TransactionResponse, TransactionUpdateRequest } from '@/types/transaction'
```

- [ ] **Step 2: Rename existing `useUpdateTransaction` → `useUpdateTransactionCategory`**

The current `useUpdateTransaction` function (lines 9–26) is the narrow category-only hook. Rename it and update its toast messages:

```ts
export function useUpdateTransactionCategory() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: { id: number; category: CategoryEnum }) => {
      const token = await getToken()
      return updateTransaction(token, payload.id, { category: payload.category })
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      toast.success('Category updated')
    },
    onError: () => {
      toast.error('Failed to update category')
    },
  })
}
```

Note: only the function name changes. Toast messages stay identical to the current implementation.

- [ ] **Step 3: Add the new `useUpdateTransaction` with full payload and optimistic update**

Add this new function immediately after `useUpdateTransactionCategory`:

```ts
export function useUpdateTransaction() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (payload: { id: number } & TransactionUpdateRequest) => {
      const { id, ...data } = payload
      const token = await getToken()
      return updateTransaction(token, id, data)
    },

    onMutate: async (payload) => {
      // Cancel in-flight queries to avoid overwriting optimistic update
      await queryClient.cancelQueries({ queryKey: ['transactions'] })

      // Snapshot all cached transaction pages for rollback
      const previousData = queryClient.getQueriesData<TransactionListResponse>({
        queryKey: ['transactions'],
      })

      const { id, ...changes } = payload

      // Merge changed fields onto the matching transaction in every cached page
      queryClient.setQueriesData<TransactionListResponse>(
        { queryKey: ['transactions'] },
        (old) => {
          if (!old) return old
          return {
            ...old,
            items: old.items.map((item) =>
              item.id === id ? { ...item, ...changes } : item
            ),
          }
        }
      )

      return { previousData }
    },

    onError: (_err, _variables, context) => {
      // Roll back all snapshots
      context?.previousData.forEach(([queryKey, data]) => {
        queryClient.setQueryData(queryKey, data)
      })
      toast.error('Failed to update transaction')
    },

    onSuccess: () => {
      toast.success('Transaction updated')
    },

    onSettled: () => {
      // Sync real server state regardless of outcome
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
    },
  })
}
```

- [ ] **Step 4: Verify TypeScript — expect one error in `category-edit-modal.tsx`**

```bash
cd web-app && npx tsc --noEmit 2>&1 | grep -E "error|warning" | head -20
```

Expected: exactly one error in `category-edit-modal.tsx` saying `useUpdateTransaction` is not exported or has wrong type. This is expected and will be fixed in the next task.

- [ ] **Step 5: Commit**

```bash
git add web-app/src/hooks/use-transaction-mutations.ts
git commit -m "feat: extract useUpdateTransactionCategory; add full useUpdateTransaction with optimistic update"
```

---

### Task 4: Update `CategoryEditModal` to use narrow hook

**Files:**
- Modify: `web-app/src/components/transactions/category-edit-modal.tsx`

- [ ] **Step 1: Swap the hook import**

In `category-edit-modal.tsx` line 19:

```ts
import { useUpdateTransaction } from '@/hooks/use-transaction-mutations'
```

Change to:

```ts
import { useUpdateTransactionCategory } from '@/hooks/use-transaction-mutations'
```

- [ ] **Step 2: Update the hook usage on line 34**

```ts
const { mutate, isPending } = useUpdateTransaction()
```

Change to:

```ts
const { mutate, isPending } = useUpdateTransactionCategory()
```

- [ ] **Step 3: Verify TypeScript — no errors**

```bash
cd web-app && npx tsc --noEmit 2>&1 | head -20
```

Expected: clean (the previous error in this file is now fixed).

- [ ] **Step 4: Commit**

```bash
git add web-app/src/components/transactions/category-edit-modal.tsx
git commit -m "fix: wire CategoryEditModal to useUpdateTransactionCategory"
```

---

## Chunk 2: UI

### Task 5: Create `EditTransactionDialog`

**Files:**
- Create: `web-app/src/components/transactions/edit-transaction-dialog.tsx`

- [ ] **Step 1: Create the file**

Create `web-app/src/components/transactions/edit-transaction-dialog.tsx` with this content:

```tsx
'use client'

import { useState, useEffect } from 'react'
import { format, parse } from 'date-fns'
import { CalendarIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Calendar } from '@/components/ui/calendar'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Checkbox } from '@/components/ui/checkbox'
import { useUpdateTransaction } from '@/hooks/use-transaction-mutations'
import { CATEGORY_OPTIONS } from '@/types/transaction'
import type { CategoryEnum, TransactionResponse, TransactionUpdateRequest } from '@/types/transaction'

interface EditTransactionDialogProps {
  transaction: TransactionResponse | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

interface FormState {
  date: string
  merchant: string
  amount: string
  category: CategoryEnum | ''
  description: string
  is_recurring: boolean
}

const EMPTY_FORM: FormState = {
  date: '',
  merchant: '',
  amount: '',
  category: '',
  description: '',
  is_recurring: false,
}

function transactionToForm(t: TransactionResponse): FormState {
  return {
    // Backend returns ISO 8601 datetime — extract the date part only
    date: t.date.split('T')[0],
    merchant: t.merchant,
    amount: t.amount,
    category: t.category,
    description: t.description ?? '',
    is_recurring: t.is_recurring,
  }
}

export function EditTransactionDialog({ transaction, open, onOpenChange }: EditTransactionDialogProps) {
  const [form, setForm] = useState<FormState>(EMPTY_FORM)
  const [calendarOpen, setCalendarOpen] = useState(false)
  const { mutate, isPending } = useUpdateTransaction()

  // Reset form whenever a different transaction is opened
  useEffect(() => {
    if (transaction) {
      setForm(transactionToForm(transaction))
    } else {
      setForm(EMPTY_FORM)
    }
  }, [transaction?.id])

  function handleOpenChange(next: boolean) {
    if (!next) setForm(EMPTY_FORM)
    onOpenChange(next)
  }

  // Build PATCH payload — only include fields that have changed
  function buildPayload(): TransactionUpdateRequest {
    if (!transaction) return {}

    const payload: TransactionUpdateRequest = {}
    const originalDate = transaction.date.split('T')[0]

    if (form.date && form.date !== originalDate) payload.date = form.date
    if (form.merchant.trim() !== transaction.merchant) payload.merchant = form.merchant.trim()
    // Compare numerically to avoid false positives from string representation differences ("-42.5" vs "-42.50")
    if (isFinite(parseFloat(form.amount)) && parseFloat(form.amount) !== parseFloat(transaction.amount)) {
      payload.amount = form.amount
    }
    if (form.category && form.category !== transaction.category) payload.category = form.category
    // Backend uses exclude_none=True so null cannot clear description — omit empty strings
    const trimmedDesc = form.description.trim()
    if (trimmedDesc !== (transaction.description ?? '')) {
      if (trimmedDesc) payload.description = trimmedDesc
    }
    if (form.is_recurring !== transaction.is_recurring) payload.is_recurring = form.is_recurring

    return payload
  }

  const changedFields = buildPayload()
  const hasChanges = Object.keys(changedFields).length > 0
  const isValid = !!(form.date && form.merchant.trim() && form.category) && isFinite(parseFloat(form.amount))

  function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!transaction || !hasChanges || !isValid) return

    mutate(
      { id: transaction.id, ...changedFields },
      { onSuccess: () => handleOpenChange(false) }
    )
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle>Edit Transaction</DialogTitle>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4 mt-2">
          {/* Date */}
          <div className="flex flex-col gap-1.5">
            <Label>Date</Label>
            <Popover open={calendarOpen} onOpenChange={setCalendarOpen}>
              <PopoverTrigger
                render={
                  <Button
                    variant="outline"
                    className="w-full justify-start text-left font-normal"
                  >
                    <CalendarIcon className="mr-2 h-4 w-4 opacity-50" />
                    {form.date
                      ? format(parse(form.date, 'yyyy-MM-dd', new Date()), 'PPP')
                      : <span className="text-muted-foreground">Pick a date</span>}
                  </Button>
                }
              />
              <PopoverContent className="w-auto p-0" align="start">
                <Calendar
                  mode="single"
                  selected={form.date ? parse(form.date, 'yyyy-MM-dd', new Date()) : undefined}
                  onSelect={(date) => {
                    if (date) setForm((f) => ({ ...f, date: format(date, 'yyyy-MM-dd') }))
                    setCalendarOpen(false)
                  }}
                />
              </PopoverContent>
            </Popover>
          </div>

          {/* Merchant */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="et-merchant">Merchant</Label>
            <Input
              id="et-merchant"
              type="text"
              placeholder="e.g. Spotify"
              value={form.merchant}
              onChange={(e) => setForm((f) => ({ ...f, merchant: e.target.value }))}
              required
            />
          </div>

          {/* Amount */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="et-amount">Amount</Label>
            <Input
              id="et-amount"
              type="number"
              step="0.01"
              placeholder="e.g. -9.99 (negative = expense)"
              value={form.amount}
              onChange={(e) => setForm((f) => ({ ...f, amount: e.target.value }))}
              required
            />
          </div>

          {/* Category */}
          <div className="flex flex-col gap-1.5">
            <Label>Category</Label>
            <Select
              value={form.category}
              onValueChange={(v) => setForm((f) => ({ ...f, category: v as CategoryEnum }))}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select category" />
              </SelectTrigger>
              <SelectContent>
                {CATEGORY_OPTIONS.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Description */}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="et-description">
              Description <span className="text-muted-foreground text-xs">(optional)</span>
            </Label>
            <Input
              id="et-description"
              type="text"
              placeholder="e.g. Monthly subscription"
              value={form.description}
              onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
            />
          </div>

          {/* Is recurring */}
          <div className="flex items-center gap-2">
            <Checkbox
              id="et-recurring"
              checked={form.is_recurring}
              onCheckedChange={(checked) =>
                setForm((f) => ({ ...f, is_recurring: checked === true }))
              }
            />
            <Label htmlFor="et-recurring" className="cursor-pointer">
              Recurring transaction
            </Label>
          </div>

          <DialogFooter showCloseButton>
            <Button type="submit" disabled={isPending || !isValid || !hasChanges}>
              {isPending ? 'Saving…' : 'Save Changes'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
```

- [ ] **Step 2: Verify TypeScript — no errors**

```bash
cd web-app && npx tsc --noEmit 2>&1 | head -20
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add web-app/src/components/transactions/edit-transaction-dialog.tsx
git commit -m "feat: add EditTransactionDialog for full single-transaction editing"
```

---

### Task 6: Update `TransactionsTable` — rename props and update call sites

**Files:**
- Modify: `web-app/src/components/transactions/transactions-table.tsx`

This task has four sub-changes, all in the same file. Apply them in order.

- [ ] **Step 1: Rename `TransactionCard`'s internal `onEdit` prop to `onEditTransaction`**

Find the `TransactionCard` function props interface (lines 32–38):

```ts
function TransactionCard({
  transaction,
  onEdit,
  onDelete,
}: {
  transaction: TransactionResponse
  onEdit: (t: TransactionResponse) => void
  onDelete: (t: TransactionResponse) => void
})
```

Change to:

```ts
function TransactionCard({
  transaction,
  onEditTransaction,
  onDelete,
}: {
  transaction: TransactionResponse
  onEditTransaction: (t: TransactionResponse) => void
  onDelete: (t: TransactionResponse) => void
})
```

- [ ] **Step 2: Update `TransactionCard` dropdown — use renamed prop**

Find the dropdown "Edit" item inside `TransactionCard` (around line 62):

```tsx
<DropdownMenuItem onClick={() => onEdit(transaction)}>
```

Change to:

```tsx
<DropdownMenuItem onClick={() => onEditTransaction(transaction)}>
```

- [ ] **Step 3: Update `TransactionsTableProps` — rename and add prop**

Find the `TransactionsTableProps` interface (lines 81–92):

```ts
export interface TransactionsTableProps {
  ...
  onEditTransaction: (transaction: TransactionResponse) => void
  onDeleteTransaction: (transaction: TransactionResponse) => void
  ...
}
```

Change `onEditTransaction` to `onEditCategory` and add `onEditTransaction`:

```ts
export interface TransactionsTableProps {
  data: TransactionResponse[]
  total: number
  offset: number
  limit: number
  page: number
  onPageChange: (page: number) => void
  onEditCategory: (transaction: TransactionResponse) => void
  onEditTransaction: (transaction: TransactionResponse) => void
  onDeleteTransaction: (transaction: TransactionResponse) => void
  onBulkRecategorize: (transactions: TransactionResponse[], resetSelection: () => void) => void
  isLoading?: boolean
}
```

- [ ] **Step 4: Update `TransactionsTable` function signature to use new prop names**

Find the destructured props in the `TransactionsTable` function (lines 96–107):

```ts
export function TransactionsTable({
  ...
  onEditTransaction,
  onDeleteTransaction,
  ...
}: TransactionsTableProps) {
```

Update to include both new props:

```ts
export function TransactionsTable({
  data,
  total,
  offset,
  limit,
  page,
  onPageChange,
  onEditCategory,
  onEditTransaction,
  onDeleteTransaction,
  onBulkRecategorize,
  isLoading,
}: TransactionsTableProps) {
```

- [ ] **Step 5: Update the category badge `onClick` — column 5 (line ~172)**

Find the category badge inside the `columns` array (column 5):

```tsx
onClick={() => onEditTransaction(info.row.original)}
```

Change to:

```tsx
onClick={() => onEditCategory(info.row.original)}
```

- [ ] **Step 6: The dropdown "Edit" item in the desktop table — no change needed**

The dropdown "Edit" `onClick` (column 7, ~line 202) currently reads `() => onEditTransaction(row.original)`. After the prop rename in `TransactionsTableProps`, `onEditTransaction` now carries the full-edit callback from `page.tsx`. No wiring change is needed here.

- [ ] **Step 7: Update `TransactionCard` instantiation in the mobile section (~line 289)**

Find:

```tsx
<TransactionCard
  key={row.id}
  transaction={row.original}
  onEdit={onEditTransaction}
  onDelete={onDeleteTransaction}
/>
```

Change to:

```tsx
<TransactionCard
  key={row.id}
  transaction={row.original}
  onEditTransaction={onEditTransaction}
  onDelete={onDeleteTransaction}
/>
```

- [ ] **Step 8: Verify TypeScript — expect errors in `page.tsx` (next task fixes them)**

```bash
cd web-app && npx tsc --noEmit 2>&1 | grep "page.tsx" | head -10
```

Expected: errors in `page.tsx` about `onEditTransaction` prop being required or unknown. This is correct — `page.tsx` still passes the old props and will be fixed in Task 7.

- [ ] **Step 9: Commit**

```bash
git add web-app/src/components/transactions/transactions-table.tsx
git commit -m "refactor: rename onEditTransaction→onEditCategory, add onEditTransaction for full edit"
```

---

### Task 7: Wire `EditTransactionDialog` in `TransactionsPage`

**Files:**
- Modify: `web-app/src/app/(app)/transactions/page.tsx`

- [ ] **Step 1: Add `EditTransactionDialog` import**

At the top of `page.tsx`, add the import alongside the other transaction component imports:

```ts
import { EditTransactionDialog } from '@/components/transactions/edit-transaction-dialog'
```

- [ ] **Step 2: Rename `editingTransaction` state → `editingCategory`**

Find (line 130):

```ts
const [editingTransaction, setEditingTransaction] = useState<TransactionResponse | null>(null)
```

Change to:

```ts
const [editingCategory, setEditingCategory] = useState<TransactionResponse | null>(null)
```

- [ ] **Step 3: Add the new `editingTransaction` state for the full-edit dialog**

Add this line directly after the renamed `editingCategory` state:

```ts
const [editingTransaction, setEditingTransaction] = useState<TransactionResponse | null>(null)
```

- [ ] **Step 4: Update the `CategoryEditModal` JSX block — all three references**

Find the `CategoryEditModal` JSX block (currently lines 334–340). It will have stale references to `editingTransaction`. Update all three:

```tsx
<CategoryEditModal
  transaction={editingCategory}
  open={editingCategory !== null}
  onOpenChange={(open) => {
    if (!open) setEditingCategory(null)
  }}
/>
```

- [ ] **Step 5: Update `TransactionsTable` prop in the main render — add `onEditCategory`**

Find the `TransactionsTable` component in the main render (around line 319). It currently passes:

```tsx
onEditTransaction={setEditingTransaction}
```

Replace with both props:

```tsx
onEditCategory={setEditingCategory}
onEditTransaction={setEditingTransaction}
```

- [ ] **Step 6: Verify there is no second `<TransactionsTable>` in the empty-state branch**

The empty-state render path (lines 217–250) renders only `<TransactionsEmptyState>` and `<AddTransactionDialog>` — there is no `<TransactionsTable>` there. No additional prop change is needed. This step is a confirmation only.

- [ ] **Step 7: Add `EditTransactionDialog` JSX alongside `CategoryEditModal`**

After the `CategoryEditModal` JSX block, add:

```tsx
<EditTransactionDialog
  transaction={editingTransaction}
  open={editingTransaction !== null}
  onOpenChange={(open) => {
    if (!open) setEditingTransaction(null)
  }}
/>
```

- [ ] **Step 8: Verify TypeScript — no errors**

```bash
cd web-app && npx tsc --noEmit 2>&1 | head -20
```

Expected: clean.

- [ ] **Step 9: Manual smoke test**

Start the dev server:

```bash
cd web-app && npm run dev
```

Verify:
1. Click the category badge on any transaction → `CategoryEditModal` opens with category-only selector; save shows "Category updated" toast ✓
2. Click the three-dot menu → "Edit" → `EditTransactionDialog` opens pre-populated with all fields ✓
3. Change a field and save → transaction updates in the table immediately (optimistic), then "Transaction updated" toast ✓
4. Open edit dialog, change nothing → "Save Changes" button is disabled ✓
5. Click the three-dot menu → "Delete" → works unchanged ✓
6. On mobile: three-dot menu → "Edit" opens full edit dialog ✓

- [ ] **Step 10: Commit**

```bash
git add web-app/src/app/(app)/transactions/page.tsx
git commit -m "feat: wire EditTransactionDialog to full-edit flow in TransactionsPage"
```
