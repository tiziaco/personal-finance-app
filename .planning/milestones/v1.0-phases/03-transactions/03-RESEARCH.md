# Phase 3: Transactions - Research

**Researched:** 2026-03-01
**Domain:** TanStack Table v8 + React Query v5 mutations + real-time filter state for a paginated, filterable, bulk-actionable transaction table in Next.js 16 / React 19
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TXN-01 | User can search transactions by merchant name with real-time filtering | `useTransactions({ merchant: debouncedQuery })` — `merchant` filter sends substring match to backend; debounce 300ms prevents over-fetching |
| TXN-02 | User can filter transactions by date range (start/end date pickers) | `TransactionFilters.date_from` / `date_to` — backend accepts ISO 8601 datetime string; `<Input type="date">` or a date picker; value passed directly to `useTransactions` filter |
| TXN-03 | User can filter transactions by category (dropdown) | `useCategories()` (Phase 1 hook) returns `CATEGORY_OPTIONS` static array; `<Select>` from `@/components/ui/select`; passes `category` filter to `useTransactions` |
| TXN-04 | User can filter by amount range (min/max inputs) | `TransactionFilters.amount_min` / `amount_max` — backend accepts string decimal; `<Input type="number">` fields, values sent as strings |
| TXN-05 | User can sort by date/amount/merchant | `TransactionFilters.sort_by` (`date` \| `amount` \| `merchant`) + `sort_order` (`asc` \| `desc`) — already on `useTransactions` |
| TXN-06 | Paginated table 25/page: Checkbox, Date, Merchant, Amount, Category, Confidence Score, Actions columns | `useReactTable` with `createColumnHelper<TransactionResponse>`, `enableRowSelection: true`, `getPaginationRowModel()`, `pageSize: 25` |
| TXN-07 | Previous/Next pagination controls + "Showing X-Y of Z" count | `table.previousPage()`, `table.nextPage()`, `table.getState().pagination.pageIndex`, total from `TransactionListResponse.total` — server-side pagination via `page` state + `useTransactions` offset |
| TXN-08 | Category edit modal — click category/edit button → modal → new category → save | `Dialog` from `@/components/ui/dialog` (base-ui backed); `useMutation` calling `updateTransaction`; `queryClient.invalidateQueries(['transactions'])` on success; `toast.success` via sonner |
| TXN-09 | Bulk recategorize via checkbox selection | `DataTableBulkActions` (already built at `@/components/ui/data-table-bulk-actions.tsx`); `useMutation` calling `batchUpdateTransactions`; `BatchUpdateRequest` shape: `{ items: [{ id, category }] }` |
| TXN-10 | Empty state with illustration and "Upload a CSV file to get started" CTA | Guard on `total === 0 && no active filters`; render illustration + `<Link href="/upload">` CTA |
</phase_requirements>

---

## Summary

Phase 3 builds the transactions page at `app/(app)/transactions/page.tsx`, which is currently a stub returning a single `<div>`. All data infrastructure is complete from Phase 1: `useTransactions` (paginated + filtered), `batchUpdateTransactions` / `updateTransaction` API functions, `BatchUpdateRequest` / `BatchUpdateResponse` types, `useCategories`, `TableSkeleton`, and `ErrorBoundary`. The page is a pure UI composition task over the existing API layer — no new dependencies are required.

The primary technical challenge is state orchestration: six independent filter states (search query, date range, category, amount range, sort, page) must be managed in the page component and forwarded to `useTransactions`. The search field requires a 300ms debounce (local state for immediate input, debounced state for the query key) to avoid over-fetching. All other filter changes should reset `page` to `0`. Pagination is **server-side** — the `useTransactions` hook already supports `page` as a second argument; there is no client-side `getPaginationRowModel` needed.

The second challenge is mutations with optimistic UI. Both `updateTransaction` (single category edit) and `batchUpdateTransactions` (bulk recategorize) must use React Query v5 `useMutation`, invalidate `['transactions']` on `onSuccess`, show a `toast.success` via sonner, and close the modal/clear the selection after success. The project already ships `DataTableBulkActions` (`@/components/ui/data-table-bulk-actions.tsx`) built on TanStack Table's `getFilteredSelectedRowModel()` — this component must be wired to the table instance.

**Primary recommendation:** Build a single `TransactionsPage` client component that owns all filter/page state, renders a `FiltersBar` for search + dropdowns, passes state to `useTransactions`, renders the TanStack Table v8 instance with row selection, drives `DataTableBulkActions` from the table instance, and opens the `CategoryEditModal` on row action. No new packages needed.

---

## Standard Stack

### Core (all already installed — no new dependencies needed)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| @tanstack/react-table | ^8.21.3 | `useReactTable`, `createColumnHelper`, row selection | Already installed; `DataTableBulkActions` already depends on it |
| @tanstack/react-query | ^5.90.21 | `useTransactions` query + `useMutation` for update/batch | Already wired; v5 `useMutation` API confirmed |
| @clerk/nextjs | ^6.38.1 | `useAuth().getToken()` inside mutation `mutationFn` | Phase 1 pattern |
| @base-ui/react | ^1.2.0 | `Dialog` (category edit modal), `Select` (category dropdown) | Project UI primitives — NOT Radix |
| sonner | ^2.0.7 | `toast.success` / `toast.error` after mutations | Already installed |
| lucide-react | ^0.575.0 | Icons: Edit2, Filter, Search, ChevronLeft, ChevronRight | Already installed |
| zod | ^4.3.6 | Optional: form validation in modal if needed | Already installed |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| shadcn/ui Input | (shadcn ^3.8.5) | Search field, amount min/max, date range inputs | All text/date/number inputs in FiltersBar |
| shadcn/ui Select | (shadcn ^3.8.5) | Category filter dropdown, category edit in modal | TXN-03, TXN-08 |
| shadcn/ui Dialog | (shadcn ^3.8.5) | Category edit modal (TXN-08) | Modal for single-transaction edit |
| shadcn/ui Button | (shadcn ^3.8.5) | Pagination controls, filter reset, modal save/cancel | All interactive buttons |
| TableSkeleton | Phase 1 built | Loading state for table area | `isLoading` from `useTransactions` |
| DataTableBulkActions | Phase 1 built | Sticky bottom bar for bulk actions | TXN-09 bulk recategorize |
| formatCurrency / formatDate | Phase 1 built (`lib/format.ts`) | Amount and date rendering in table cells | All table amount/date cells |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Server-side pagination (current) | Client-side `getPaginationRowModel()` | Server-side is correct — dataset can be large; don't fetch all rows |
| Custom debounce hook | `use-debounce` npm package | No new dep needed; ~5-line `useEffect` in hook or inline is sufficient |
| `<select>` HTML element | `Combobox` from @base-ui | `Select` is already installed and styled; `Combobox` only needed if user can type to search the dropdown |

**Installation:** No new packages. Phase 3 uses only what Phase 1 installed.

---

## Architecture Patterns

### Recommended Project Structure

```
web-app/src/
├── app/(app)/transactions/
│   └── page.tsx                        # 'use client' — owns all filter/page state
├── components/transactions/
│   ├── transactions-table.tsx          # TanStack Table instance + rows
│   ├── filters-bar.tsx                 # Search, date range, category, amount, sort controls
│   ├── category-edit-modal.tsx         # TXN-08: Dialog with category Select + save mutation
│   └── transactions-empty-state.tsx    # TXN-10: illustration + Upload CTA
├── hooks/
│   └── use-transaction-mutations.ts    # useMutation wrappers for updateTransaction + batchUpdate
```

### Pattern 1: Server-Side Pagination with Filter State

**What:** All filter state lives in `TransactionsPage`. Page resets to `0` whenever any filter changes. The `page` variable is passed as the second argument to `useTransactions`.

**When to use:** TXN-01 through TXN-07.

```tsx
// web-app/src/app/(app)/transactions/page.tsx
'use client'

import { useState } from 'react'
import { useTransactions } from '@/hooks/use-transactions'
import type { TransactionFilters } from '@/types/transaction'

export default function TransactionsPage() {
  // Raw search input (immediate — drives the displayed input value)
  const [searchInput, setSearchInput] = useState('')
  // Debounced search query (used in query key after 300ms idle)
  const [debouncedSearch, setDebouncedSearch] = useState('')
  const [dateFrom, setDateFrom] = useState<string | undefined>()
  const [dateTo, setDateTo] = useState<string | undefined>()
  const [category, setCategory] = useState<string | undefined>()
  const [amountMin, setAmountMin] = useState<string | undefined>()
  const [amountMax, setAmountMax] = useState<string | undefined>()
  const [sortBy, setSortBy] = useState<'date' | 'amount' | 'merchant'>('date')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(0)

  const filters: TransactionFilters = {
    merchant: debouncedSearch || undefined,
    date_from: dateFrom,
    date_to: dateTo,
    category: category as TransactionFilters['category'],
    amount_min: amountMin,
    amount_max: amountMax,
    sort_by: sortBy,
    sort_order: sortOrder,
    limit: 25,
  }

  const { data, isLoading } = useTransactions(filters, page)

  // Reset page when filters change
  const handleFilterChange = (update: Partial<typeof filters>) => {
    setPage(0)
    // apply individual setters
  }

  // ...render FiltersBar + TransactionsTable + pagination
}
```

### Pattern 2: Debounce Search Without a Library

**What:** A small `useDebounce` hook that delays committing the search value to the query key.

**When to use:** TXN-01 real-time merchant search.

```typescript
// web-app/src/hooks/use-debounce.ts
import { useState, useEffect } from 'react'

export function useDebounce<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState<T>(value)
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return debounced
}
```

Usage in `TransactionsPage`:
```tsx
const [searchInput, setSearchInput] = useState('')
const debouncedSearch = useDebounce(searchInput, 300)
// filters.merchant = debouncedSearch || undefined
```

### Pattern 3: TanStack Table v8 with Row Selection

**What:** `createColumnHelper` for typed columns + `useReactTable` with `enableRowSelection: true` + `getCoreRowModel()`. Pagination is server-side — do NOT use `getPaginationRowModel()`.

**When to use:** TXN-06 (table), TXN-07 (pagination), TXN-09 (bulk select).

```tsx
// web-app/src/components/transactions/transactions-table.tsx
'use client'
import {
  createColumnHelper,
  useReactTable,
  getCoreRowModel,
  getFilteredRowModel,
  flexRender,
  type RowSelectionState,
} from '@tanstack/react-table'
import { useState } from 'react'
import type { TransactionResponse } from '@/types/transaction'
import { formatCurrency, formatDate } from '@/lib/format'
import { DataTableBulkActions } from '@/components/ui/data-table-bulk-actions'

const columnHelper = createColumnHelper<TransactionResponse>()

const columns = [
  // Checkbox column (select all / select row)
  columnHelper.display({
    id: 'select',
    header: ({ table }) => (
      <input
        type="checkbox"
        checked={table.getIsAllPageRowsSelected()}
        ref={(el) => {
          if (el) el.indeterminate = table.getIsSomePageRowsSelected()
        }}
        onChange={table.getToggleAllPageRowsSelectedHandler()}
      />
    ),
    cell: ({ row }) => (
      <input
        type="checkbox"
        checked={row.getIsSelected()}
        onChange={row.getToggleSelectedHandler()}
      />
    ),
  }),
  columnHelper.accessor('date', {
    header: 'Date',
    cell: (info) => formatDate(info.getValue()),
  }),
  columnHelper.accessor('merchant', { header: 'Merchant' }),
  columnHelper.accessor('amount', {
    header: 'Amount',
    cell: (info) => formatCurrency(info.getValue()),
  }),
  columnHelper.accessor('category', { header: 'Category' }),
  columnHelper.accessor('confidence_score', {
    header: 'Confidence',
    cell: (info) => `${(info.getValue() * 100).toFixed(0)}%`,
  }),
  columnHelper.display({
    id: 'actions',
    header: 'Actions',
    cell: ({ row }) => <EditButton transaction={row.original} />,
  }),
]

interface TransactionsTableProps {
  data: TransactionResponse[]
}

export function TransactionsTable({ data }: TransactionsTableProps) {
  const [rowSelection, setRowSelection] = useState<RowSelectionState>({})

  const table = useReactTable({
    data,
    columns,
    state: { rowSelection },
    onRowSelectionChange: setRowSelection,
    enableRowSelection: true,
    getCoreRowModel: getCoreRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    // NOTE: No getPaginationRowModel — pagination is server-side
    getRowId: (row) => String(row.id), // stable ID for selection
  })

  return (
    <>
      <table>
        <thead>
          {table.getHeaderGroups().map(headerGroup => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map(header => (
                <th key={header.id}>
                  {flexRender(header.column.columnDef.header, header.getContext())}
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map(row => (
            <tr key={row.id}>
              {row.getVisibleCells().map(cell => (
                <td key={cell.id}>
                  {flexRender(cell.column.columnDef.cell, cell.getContext())}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>

      {/* Sticky bulk actions bar — only renders when rows are selected */}
      <DataTableBulkActions
        table={table}
        actions={[{
          label: 'Recategorize',
          onClick: (selectedRows, resetSelection) => {
            // Open bulk category modal
          }
        }]}
      />
    </>
  )
}
```

### Pattern 4: Single-Transaction Category Edit Mutation

**What:** `useMutation` wrapping `updateTransaction`, with `onSuccess` invalidating `['transactions']` and showing a toast. The modal closes on success by clearing the selected transaction.

**When to use:** TXN-08.

```typescript
// web-app/src/hooks/use-transaction-mutations.ts
'use client'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useAuth } from '@clerk/nextjs'
import { toast } from 'sonner'
import { updateTransaction, batchUpdateTransactions } from '@/lib/api/transactions'
import type { CategoryEnum } from '@/types/transaction'

export function useUpdateTransaction() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ id, category }: { id: number; category: CategoryEnum }) => {
      const token = await getToken()
      return updateTransaction(token, id, { category })
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

export function useBatchUpdateTransactions() {
  const { getToken } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async (items: Array<{ id: number; category: CategoryEnum }>) => {
      const token = await getToken()
      return batchUpdateTransactions(token, { items })
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['transactions'] })
      toast.success(`${data.updated} transactions updated`)
    },
    onError: () => {
      toast.error('Bulk update failed')
    },
  })
}
```

### Pattern 5: Category Edit Modal Using base-ui Dialog

**What:** The project uses `@base-ui/react/dialog` (NOT Radix), wrapped in `@/components/ui/dialog`. The component renders `Dialog`, `DialogContent`, `DialogHeader`, `DialogTitle`, `DialogFooter` from that local wrapper.

**When to use:** TXN-08. Critical: use project's `dialog.tsx`, not a raw Radix or HTML dialog.

```tsx
// web-app/src/components/transactions/category-edit-modal.tsx
'use client'
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from '@/components/ui/dialog'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { CATEGORY_OPTIONS, type CategoryEnum, type TransactionResponse } from '@/types/transaction'
import { useState } from 'react'
import { useUpdateTransaction } from '@/hooks/use-transaction-mutations'
import { formatCurrency, formatDate } from '@/lib/format'

interface CategoryEditModalProps {
  transaction: TransactionResponse | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function CategoryEditModal({ transaction, open, onOpenChange }: CategoryEditModalProps) {
  const [selectedCategory, setSelectedCategory] = useState<CategoryEnum | undefined>()
  const { mutate, isPending } = useUpdateTransaction()

  const handleSave = () => {
    if (!transaction || !selectedCategory) return
    mutate(
      { id: transaction.id, category: selectedCategory },
      { onSuccess: () => onOpenChange(false) }
    )
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Category</DialogTitle>
        </DialogHeader>
        {transaction && (
          <div className="space-y-4">
            <div className="text-sm text-muted-foreground">
              <p>{transaction.merchant}</p>
              <p>{formatCurrency(transaction.amount)} &middot; {formatDate(transaction.date)}</p>
            </div>
            <Select
              value={selectedCategory ?? transaction.category}
              onValueChange={(val) => setSelectedCategory(val as CategoryEnum)}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select category" />
              </SelectTrigger>
              <SelectContent>
                {CATEGORY_OPTIONS.map((cat) => (
                  <SelectItem key={cat} value={cat}>{cat}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}
        <DialogFooter showCloseButton>
          <Button onClick={handleSave} disabled={isPending || !selectedCategory}>
            {isPending ? 'Saving…' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
```

### Pattern 6: Pagination Controls (Server-Side)

**What:** Page state is in `TransactionsPage`. Prev/Next buttons call `setPage`. "Showing X-Y of Z" is derived from `data.offset`, `data.limit`, `data.total`.

**When to use:** TXN-07.

```tsx
// In TransactionsPage
const totalPages = data ? Math.ceil(data.total / 25) : 0
const currentPage = page // 0-indexed

// UI
<div className="flex items-center justify-between">
  <span className="text-sm text-muted-foreground">
    Showing {data ? data.offset + 1 : 0}–{data ? Math.min(data.offset + data.limit, data.total) : 0} of {data?.total ?? 0} transactions
  </span>
  <div className="flex items-center gap-2">
    <Button
      variant="outline"
      size="sm"
      onClick={() => setPage(p => Math.max(0, p - 1))}
      disabled={page === 0}
    >
      Previous
    </Button>
    <span className="text-sm">Page {page + 1} of {totalPages}</span>
    <Button
      variant="outline"
      size="sm"
      onClick={() => setPage(p => p + 1)}
      disabled={!data || (page + 1) * 25 >= data.total}
    >
      Next
    </Button>
  </div>
</div>
```

### Pattern 7: Empty State Guard

**What:** Render `TransactionsEmptyState` only when no transactions exist AND no filters are active (to avoid confusing "no results" with "no data").

**When to use:** TXN-10.

```tsx
const hasActiveFilters = !!(debouncedSearch || dateFrom || dateTo || category || amountMin || amountMax)
const isEmpty = !isLoading && data?.total === 0

if (isEmpty && !hasActiveFilters) {
  return <TransactionsEmptyState />
}
// For empty results with active filters, show a "no results" message instead
```

### Anti-Patterns to Avoid

- **Using `getPaginationRowModel()` from TanStack Table:** Pagination is server-side. The table renders only the 25 rows returned by the API for the current page. Do NOT load all pages client-side.
- **Putting `getToken()` in hook body (outside `mutationFn`):** Token is not stable — it must be called inside `mutationFn`, matching the established Phase 1 pattern for React Query hooks.
- **Using `<select>` HTML element instead of `<Select>` shadcn component:** All dropdowns must use `@/components/ui/select` to match project styling.
- **Using Radix Dialog primitives directly:** The project wraps `@base-ui/react/dialog`, not Radix. The `Dialog` import must come from `@/components/ui/dialog`.
- **Resetting selection state after invalidation without `resetRowSelection()`:** TanStack Table's row selection state (keyed by row ID) persists across re-renders. After a bulk mutation succeeds, call `table.resetRowSelection()` (already wired in `DataTableBulkActions`'s `onClick`).
- **Showing empty state when filters are active:** `data.total === 0` with active filters means "no results for these filters" — show a "no matching transactions" message, NOT the "Upload CSV" empty state.
- **`amount` filter values must be strings:** `TransactionFilters.amount_min` / `amount_max` are typed as `string | undefined` — they are passed as query string params, not numbers. Match the existing `TransactionFilters` TypeScript interface.
- **Debouncing with `Date` or timer ID stored in refs without cleanup:** Use the `useEffect` + `clearTimeout` pattern; missing cleanup causes stale updates when the component unmounts mid-debounce.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Sticky bulk action bar with selected count + action buttons | Custom overlay component | `DataTableBulkActions` (`@/components/ui/data-table-bulk-actions.tsx`) | Already built; expects `Table<TData>` + `BulkAction[]` — wire it directly |
| Table row selection state management | Custom `Set<number>` with toggle handlers | TanStack Table `enableRowSelection` + `rowSelection` state | TanStack handles indeterminate checkbox, select-all per page, `getFilteredSelectedRowModel()` |
| Category edit modal | Custom `<dialog>` or portal | `Dialog` / `DialogContent` from `@/components/ui/dialog` | base-ui animated, focus-trapped, with close button and overlay |
| Category dropdown | Custom `<select>` or list | `Select` / `SelectContent` / `SelectItem` from `@/components/ui/select` | Already installed; matches design system |
| Amount/date formatting | Custom format functions | `formatCurrency()`, `formatDate()` from `@/lib/format` | Already built in Phase 1 with de-DE / EUR locale |
| Loading state for table | Custom shimmer rows | `TableSkeleton` (`@/components/shared/skeletons/table-skeleton.tsx`) | Parameterizable: `<TableSkeleton rows={25} columns={7} />` |
| Debounced search value | `use-debounce` npm package | 5-line `useDebounce` hook in `hooks/use-debounce.ts` | Zero new dependency; simple `useEffect` + `clearTimeout` |
| React Query mutations with toast | Custom fetch + state | `useMutation` from `@tanstack/react-query` with `onSuccess` / `onError` | v5 pattern; handles loading, error, success lifecycle |

**Key insight:** Phase 1 deliberately built the primitives Phase 3 consumes. The bulk actions bar is already in the codebase and expects a TanStack Table instance — use it directly.

---

## Common Pitfalls

### Pitfall 1: Server vs. Client Pagination Confusion

**What goes wrong:** Developer passes `getPaginationRowModel()` to `useReactTable` and calls `table.previousPage()` instead of managing server-side page state.

**Why it happens:** TanStack Table has built-in client-side pagination; it's tempting to use it.

**How to avoid:** The backend returns `total`, `offset`, `limit` — pagination is server-side. The table instance receives only the 25 rows for the current page. Manage `page` in React state; pass it to `useTransactions(filters, page)`. Do NOT use `getPaginationRowModel()`.

**Warning signs:** All rows appear on page 1 regardless of the backend `total`; or the table tries to paginate within the 25 already-fetched rows.

### Pitfall 2: Row Selection State Keyed Wrong

**What goes wrong:** After a mutation, selected rows in TanStack Table appear deselected even though `rowSelection` state still has entries — or vice versa.

**Why it happens:** TanStack Table keys row selection by the row ID. If `getRowId` is not set, it defaults to the row index, which changes when the data array changes after `invalidateQueries` re-fetch.

**How to avoid:** Always set `getRowId: (row) => String(row.id)` in `useReactTable` so selection is keyed by the stable transaction `id`, not its index.

**Warning signs:** Selections appear to jump to wrong rows after a data refresh.

### Pitfall 3: Bulk Action resetSelection Not Called

**What goes wrong:** After a successful bulk recategorize, the "X selected" bar stays visible even though the mutation is complete.

**Why it happens:** `DataTableBulkActions` passes `resetSelection` to the `onClick` callback, but the handler doesn't call it.

**How to avoid:** In the bulk action `onClick` handler: `onClick: (selectedRows, resetSelection) => { mutate(items, { onSuccess: () => resetSelection() }) }`. The `resetSelection` function calls `table.resetRowSelection()` internally.

**Warning signs:** After a successful bulk mutation, the sticky bar persists with a stale selected count.

### Pitfall 4: Empty State vs. No Results Confusion

**What goes wrong:** When a user types a search term that matches nothing, the page shows "Upload a CSV file to get started" instead of "No transactions found."

**Why it happens:** Both cases have `data.total === 0`, but only one should show the upload CTA.

**How to avoid:** Gate the `TransactionsEmptyState` (with Upload CTA) on `total === 0 AND !hasActiveFilters`. For `total === 0 AND hasActiveFilters`, show a separate "No transactions match your filters" UI with a "Clear filters" button.

**Warning signs:** Users see the upload CTA after filtering returns empty results.

### Pitfall 5: Filter Change Without Page Reset

**What goes wrong:** User is on page 3, changes the category filter, and still sees page 3 — but after filtering, page 3 may not exist, resulting in an empty table or a fetched offset beyond `total`.

**Why it happens:** Forgetting to call `setPage(0)` when any filter state changes.

**How to avoid:** All filter setter calls must also call `setPage(0)`. A clean pattern is a `handleFilterChange` wrapper that accepts partial filter updates, applies them to state, and always resets page.

**Warning signs:** Table shows no rows after filter change even though the first page would have results.

### Pitfall 6: Dialog open State Not Reset on Close

**What goes wrong:** User edits a transaction category, saves, closes the modal. Then opens another transaction's modal — but the dropdown pre-populates with the *previous* transaction's newly set category rather than the current one.

**Why it happens:** `selectedCategory` state in the modal is not reset when a new transaction is opened.

**How to avoid:** Use a `useEffect` in `CategoryEditModal` to reset `selectedCategory` to `undefined` whenever the `transaction` prop changes, OR initialize `selectedCategory` as `undefined` and always fall back to `transaction.category` for the current value.

**Warning signs:** Editing transaction A then opening transaction B shows A's edited category as the initial selection.

### Pitfall 7: `amount_min`/`amount_max` Typed as Number in Input

**What goes wrong:** `<input type="number" onChange={(e) => setAmountMin(Number(e.target.value))}` — but `TransactionFilters.amount_min` is `string | undefined`. TypeScript error or silent type mismatch.

**Why it happens:** HTML `<input type="number">` suggests numeric values, and `TransactionFilters` was intentionally typed as `string` (backend accepts string decimal).

**How to avoid:** Keep `amountMin` / `amountMax` state as `string | undefined`. Use `e.target.value` directly (it is already a string). Convert to `undefined` when empty: `value || undefined`.

**Warning signs:** TypeScript error on `amount_min: amountMin` where `amountMin` is `number`.

---

## Code Examples

### Complete Filter State Reset on Change

```typescript
// In TransactionsPage — DRY helper to apply filter updates and always reset page
function updateFilter(update: Partial<TransactionFilters>) {
  setPage(0)
  if ('merchant' in update) setMerchantInput(update.merchant ?? '')
  if ('category' in update) setCategory(update.category)
  if ('date_from' in update) setDateFrom(update.date_from)
  if ('date_to' in update) setDateTo(update.date_to)
  if ('amount_min' in update) setAmountMin(update.amount_min)
  if ('amount_max' in update) setAmountMax(update.amount_max)
}
```

### BatchUpdateRequest Shape (Confirmed from Backend)

```typescript
// Confirmed from server/app/schemas/transaction.py
// BatchUpdateItem can update any field — for bulk recategorize, only id + category needed
const body: BatchUpdateRequest = {
  items: selectedTransactions.map(txn => ({
    id: txn.id,
    category: newCategory, // CategoryEnum
  }))
}
// POST PATCH /api/v1/transactions/batch
// Response: { updated: number }
// Max 100 items per request — enforce in UI if selection > 100
```

### getRowId for Stable Selection

```typescript
// Source: TanStack Table v8 docs — Table Instance Guide
const table = useReactTable({
  data,
  columns,
  state: { rowSelection },
  onRowSelectionChange: setRowSelection,
  enableRowSelection: true,
  getCoreRowModel: getCoreRowModel(),
  getFilteredRowModel: getFilteredRowModel(),
  getRowId: (row) => String(row.id), // critical for stable selection after re-fetch
})
```

### useMutation with React Query v5 (Project Pattern)

```typescript
// Source: React Query v5 docs + Phase 1 established pattern
// getToken() MUST be inside mutationFn — not in hook body (token is not stable)
const mutation = useMutation({
  mutationFn: async (payload: ...) => {
    const token = await getToken()  // inside mutationFn
    return apiFunction(token, payload)
  },
  onSuccess: () => {
    queryClient.invalidateQueries({ queryKey: ['transactions'] })
    toast.success('...')
  },
  onError: () => {
    toast.error('...')
  },
})
```

### Showing X–Y of Z Transactions

```typescript
// Source: derived from TransactionListResponse shape (confirmed from backend schema)
const from = data ? data.offset + 1 : 0
const to = data ? Math.min(data.offset + data.limit, data.total) : 0
const total = data?.total ?? 0
// "Showing 26–50 of 143 transactions"
```

---

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `react-table` v7 hooks API | TanStack Table v8 `useReactTable` + `createColumnHelper` | v8 is the current release (^8.21.3 installed); v7 is legacy — confirmed in package.json |
| `useMutation({ mutationFn: ... })` with `.mutate()` returning `void` | v5: `.mutate()` still `void`; use `onSuccess` callback or `mutateAsync()` for Promise | v5 removes `onSuccess` from `.mutate()` signature — pass callbacks in `useMutation({})` definition |
| Inline `setTimeout` debounce in component | `useDebounce` custom hook | Separates concern; reusable; consistent 300ms delay across search fields |
| `hsl(var(--chart-N))` color tokens | `var(--chart-N)` directly (Tailwind v4 OKLCH) | Established in Phase 1 — only relevant if any chart-adjacent visuals appear |

**Deprecated/outdated:**
- `getPaginationRowModel()` from TanStack Table: still valid for client-side pagination, but NOT appropriate here — backend handles pagination.
- `react-table` v7 imports (`useTable`, `usePagination`, `useRowSelect`): not installed; this project uses v8.

---

## Open Questions

1. **Batch operation size limit enforcement**
   - What we know: `BatchUpdateRequest.items` has `max_length=100` on the backend (confirmed from `server/app/schemas/transaction.py`).
   - What's unclear: Should the UI prevent selecting more than 100 rows, or silently split into batches?
   - Recommendation: Disable the select-all checkbox or cap selection at 100 in the `DataTableBulkActions` onClick handler with a `toast.error('Maximum 100 transactions can be recategorized at once')` guard. Batching adds complexity not required by TXN-09.

2. **Confidence score display threshold**
   - What we know: `confidence_score` is `float` (0.0–1.0). TXN-06 says "Confidence Score" column. No visual threshold is specified in requirements.
   - What's unclear: Should low-confidence rows be visually flagged (e.g., yellow badge)?
   - Recommendation: Display as percentage (`(score * 100).toFixed(0) + '%'`). Add a subtle color indicator only if time permits in a later polish wave; do not block TXN-06 on this decision.

3. **Sort UI pattern**
   - What we know: TXN-05 requires sorting by date/amount/merchant. The filter bar already handles categorical filters.
   - What's unclear: Should sorting be column header click (common table pattern) or a dedicated sort dropdown in the filters bar?
   - Recommendation: Add a dedicated "Sort by" dropdown in the `FiltersBar` for v1 — it avoids adding click handlers to every column header and is simpler to implement. Column-header sorting can be a v2 enhancement.

---

## Sources

### Primary (HIGH confidence)
- `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/src/hooks/use-transactions.ts` — hook signature, filter interface, page parameter
- `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/src/types/transaction.ts` — `TransactionResponse`, `TransactionFilters`, `BatchUpdateRequest`, `CATEGORY_OPTIONS`
- `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/src/lib/api/transactions.ts` — `updateTransaction`, `batchUpdateTransactions` function signatures
- `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/api/v1/transactions.py` — backend endpoint shapes confirmed; `PATCH /batch` body = `{ items: [{ id, category?, ... }] }`; max 100 items
- `/Users/tizianoiacovelli/projects/personal-finance-app/server/app/schemas/transaction.py` — `BatchUpdateItem`, `BatchUpdateRequest`, `TransactionFilters` with all supported filter params
- `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/src/components/ui/data-table-bulk-actions.tsx` — `DataTableBulkActions` already implemented with `Table<TData>` + `BulkAction[]` API
- `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/src/components/ui/dialog.tsx` — project Dialog is base-ui backed, not Radix
- `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/src/components/ui/select.tsx` — project Select is base-ui backed
- `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/package.json` — `@tanstack/react-table: ^8.21.3`, no additional deps needed
- `/Users/tizianoiacovelli/projects/personal-finance-app/web-app/src/lib/format.ts` — `formatCurrency`, `formatDate` already built
- `/Users/tizianoiacovelli/projects/personal-finance-app/.planning/STATE.md` — EUR/de-DE locale decision, `getToken()` inside `queryFn` pattern, string amounts

### Secondary (MEDIUM confidence)
- [TanStack Table v8 Row Selection Guide](https://tanstack.com/table/v8/docs/guide/row-selection) — `enableRowSelection`, `getToggleAllPageRowsSelectedHandler`, `getFilteredSelectedRowModel`, `getRowId` — confirmed via WebSearch against official docs URL
- [TanStack React Query v5 useMutation docs](https://tanstack.com/query/v5/docs/react/guides/mutations) — `onSuccess` with `invalidateQueries` pattern confirmed via WebSearch
- [TanStack React Query v5 Invalidations from Mutations](https://tanstack.com/query/v5/docs/react/guides/invalidations-from-mutations) — `queryClient.invalidateQueries({ queryKey: [...] })` v5 object syntax confirmed

### Tertiary (LOW confidence)
- None — all findings grounded in project source files or official TanStack docs

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries confirmed from package.json; no new dependencies
- Backend API shapes: HIGH — read directly from server Python schemas and route file
- TanStack Table v8 patterns: HIGH — confirmed from official docs URLs; `DataTableBulkActions` in codebase shows the exact API shape in use
- Architecture: HIGH — page is a stub; all primitives exist; composition is the task
- Pitfalls: HIGH — derived from project decisions in STATE.md + established Phase 1 patterns + TanStack Table selection gotchas

**Research date:** 2026-03-01
**Valid until:** 2026-04-01 (30 days — stable stack; backend is finalized)
