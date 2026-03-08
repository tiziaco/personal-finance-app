'use client'

import { useState } from 'react'
import { useSearchParams } from 'next/navigation'
import { useTransactions } from '@/hooks/use-transactions'
import { useDebounce } from '@/hooks/use-debounce'
import { useBatchUpdateTransactions } from '@/hooks/use-transaction-mutations'
import { FiltersBar } from '@/components/transactions/filters-bar'
import { TransactionsTable } from '@/components/transactions/transactions-table'
import { CategoryEditModal } from '@/components/transactions/category-edit-modal'
import { TransactionsEmptyState } from '@/components/transactions/transactions-empty-state'
import { CSVUploadDialog } from '@/components/transactions/csv-upload-dialog'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Button } from '@/components/ui/button'
import { ErrorBoundary } from '@/components/shared/error-boundary'
import type { CategoryEnum, TransactionResponse, TransactionFilters } from '@/types/transaction'
import { CATEGORY_OPTIONS } from '@/types/transaction'

// ---------------------------------------------------------------------------
// BulkCategoryModal — local component, not exported
// ---------------------------------------------------------------------------

interface BulkCategoryModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
  transactions: TransactionResponse[]
  onSave: (category: CategoryEnum) => void
  isPending: boolean
}

function BulkCategoryModal({
  open,
  onOpenChange,
  transactions,
  onSave,
  isPending,
}: BulkCategoryModalProps) {
  const [selectedCategory, setSelectedCategory] = useState<CategoryEnum | ''>('')

  const handleSave = () => {
    if (selectedCategory === '') return
    onSave(selectedCategory)
  }

  // Reset selection when modal closes
  const handleOpenChange = (nextOpen: boolean) => {
    if (!nextOpen) setSelectedCategory('')
    onOpenChange(nextOpen)
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Recategorize {transactions.length} transaction{transactions.length !== 1 ? 's' : ''}</DialogTitle>
        </DialogHeader>

        <Select
          value={selectedCategory}
          onValueChange={(value) => {
            if (value) setSelectedCategory(value as CategoryEnum)
          }}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Select a category" />
          </SelectTrigger>
          <SelectContent>
            {CATEGORY_OPTIONS.map((cat) => (
              <SelectItem key={cat} value={cat}>
                {cat}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <DialogFooter showCloseButton>
          <Button onClick={handleSave} disabled={isPending || selectedCategory === ''}>
            {isPending ? 'Saving…' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

// ---------------------------------------------------------------------------
// TransactionsPage — filter state owner and page composition
// ---------------------------------------------------------------------------

export default function TransactionsPage() {
  const searchParams = useSearchParams()

  // Filter state
  const [searchInput, setSearchInput] = useState('')
  const debouncedSearch = useDebounce(searchInput, 300)
  const [dateFrom, setDateFrom] = useState<string | undefined>()
  const [dateTo, setDateTo] = useState<string | undefined>()
  const [category, setCategory] = useState<CategoryEnum | undefined>()
  const [amountMin, setAmountMin] = useState<string | undefined>()
  const [amountMax, setAmountMax] = useState<string | undefined>()
  const [isRecurring, setIsRecurring] = useState<boolean | undefined>(() => {
    const v = searchParams.get('is_recurring')
    return v === 'true' ? true : v === 'false' ? false : undefined
  })
  const [sortBy, setSortBy] = useState<'date' | 'amount' | 'merchant'>('date')
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc')
  const [page, setPage] = useState(0)

  // Modal state
  const [uploadOpen, setUploadOpen] = useState(false)
  const [editingTransaction, setEditingTransaction] = useState<TransactionResponse | null>(null)
  const [bulkModalOpen, setBulkModalOpen] = useState(false)
  const [bulkTransactions, setBulkTransactions] = useState<TransactionResponse[]>([])
  const [bulkResetFn, setBulkResetFn] = useState<(() => void) | null>(null)

  // CRITICAL: filter reset helper — any filter change resets page to 0 to avoid stale offset
  function updateFilter(update: {
    search?: string
    dateFrom?: string
    dateTo?: string
    category?: CategoryEnum
    amountMin?: string
    amountMax?: string
    isRecurring?: boolean
    sortBy?: 'date' | 'amount' | 'merchant'
    sortOrder?: 'asc' | 'desc'
  }) {
    setPage(0)
    if ('search' in update) setSearchInput(update.search ?? '')
    if ('dateFrom' in update) setDateFrom(update.dateFrom)
    if ('dateTo' in update) setDateTo(update.dateTo)
    if ('category' in update) setCategory(update.category)
    if ('amountMin' in update) setAmountMin(update.amountMin)
    if ('amountMax' in update) setAmountMax(update.amountMax)
    if ('isRecurring' in update) setIsRecurring(update.isRecurring)
    if ('sortBy' in update) setSortBy(update.sortBy ?? 'date')
    if ('sortOrder' in update) setSortOrder(update.sortOrder ?? 'desc')
  }

  function clearAllFilters() {
    setSearchInput('')
    setDateFrom(undefined)
    setDateTo(undefined)
    setCategory(undefined)
    setAmountMin(undefined)
    setAmountMax(undefined)
    setIsRecurring(undefined)
    setSortBy('date')
    setSortOrder('desc')
    setPage(0)
  }

  // Data fetching
  const filters: TransactionFilters = {
    merchant: debouncedSearch || undefined,
    date_from: dateFrom,
    date_to: dateTo,
    category,
    amount_min: amountMin,
    amount_max: amountMax,
    is_recurring: isRecurring,
    sort_by: sortBy,
    sort_order: sortOrder,
  }
  const { data, isLoading } = useTransactions(filters, page)

  // Active filter detection — gates empty state display (research pitfall #4)
  const hasActiveFilters = !!(debouncedSearch || dateFrom || dateTo || category || amountMin || amountMax || isRecurring !== undefined)
  const isEmpty = !isLoading && data?.total === 0

  // Bulk recategorize
  const batchMutation = useBatchUpdateTransactions()

  function handleBulkRecategorize(transactions: TransactionResponse[], resetSelection: () => void) {
    setBulkTransactions(transactions)
    setBulkResetFn(() => resetSelection)
    setBulkModalOpen(true)
  }

  function handleBulkSave(category: CategoryEnum) {
    const items = bulkTransactions.map((t) => ({ id: t.id, category }))
    batchMutation.mutate(items, {
      onSuccess: () => {
        bulkResetFn?.()
        setBulkModalOpen(false)
      },
    })
  }

  // Empty state — no transactions and no active filters
  if (isEmpty && !hasActiveFilters) {
    return (
      <div className="container max-w-6xl mx-auto py-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-2xl font-bold">Transactions</h1>
          <Button variant="outline" size="sm" onClick={() => setUploadOpen(true)}>
            Import CSV
          </Button>
        </div>
        <TransactionsEmptyState />
        <CSVUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />
      </div>
    )
  }

  return (
    <ErrorBoundary>
      <div className="container max-w-6xl mx-auto py-8 space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Transactions</h1>
          <Button variant="outline" size="sm" onClick={() => setUploadOpen(true)}>
            Import CSV
          </Button>
        </div>

        <ErrorBoundary>
          <FiltersBar
            searchInput={searchInput}
            onSearchChange={(v) => updateFilter({ search: v })}
            dateFrom={dateFrom}
            onDateFromChange={(v) => updateFilter({ dateFrom: v })}
            dateTo={dateTo}
            onDateToChange={(v) => updateFilter({ dateTo: v })}
            category={category}
            onCategoryChange={(v) => updateFilter({ category: v })}
            amountMin={amountMin}
            onAmountMinChange={(v) => updateFilter({ amountMin: v })}
            amountMax={amountMax}
            onAmountMaxChange={(v) => updateFilter({ amountMax: v })}
            isRecurring={isRecurring}
            onIsRecurringChange={(v) => updateFilter({ isRecurring: v })}
            sortBy={sortBy}
            onSortByChange={(v) => updateFilter({ sortBy: v })}
            sortOrder={sortOrder}
            onSortOrderChange={(v) => updateFilter({ sortOrder: v })}
            onClearAll={clearAllFilters}
            hasActiveFilters={hasActiveFilters}
          />
        </ErrorBoundary>

        {/* No-results state — filters active but zero results */}
        {isEmpty && hasActiveFilters && (
          <div className="text-center py-16 text-muted-foreground">
            <p className="text-sm">No transactions match your filters.</p>
            <button onClick={clearAllFilters} className="text-sm underline mt-2">
              Clear filters
            </button>
          </div>
        )}

        {!isEmpty && (
          <ErrorBoundary>
            <TransactionsTable
              data={data?.items ?? []}
              total={data?.total ?? 0}
              offset={data?.offset ?? 0}
              limit={data?.limit ?? 25}
              page={page}
              onPageChange={setPage}
              onEditTransaction={setEditingTransaction}
              onBulkRecategorize={handleBulkRecategorize}
              isLoading={isLoading}
            />
          </ErrorBoundary>
        )}

        <CSVUploadDialog open={uploadOpen} onOpenChange={setUploadOpen} />

        <CategoryEditModal
          transaction={editingTransaction}
          open={editingTransaction !== null}
          onOpenChange={(open) => {
            if (!open) setEditingTransaction(null)
          }}
        />

        <BulkCategoryModal
          open={bulkModalOpen}
          onOpenChange={setBulkModalOpen}
          transactions={bulkTransactions}
          onSave={handleBulkSave}
          isPending={batchMutation.isPending}
        />
      </div>
    </ErrorBoundary>
  )
}
