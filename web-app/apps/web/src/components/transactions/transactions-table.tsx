"use client"

import { useCallback, useState } from "react"
import { PlusIcon, Trash2 } from "lucide-react"
import { keepPreviousData } from "@tanstack/react-query"
import {
  useListTransactions,
  useUpdateTransaction,
} from "@app/api-client/endpoints/transactions"
import type { Category, TransactionResponse } from "@app/api-client/types"
import { ServerDataTable } from "@app/data-table/server-data-table"
import { TableSearchInput } from "@app/data-table/table-search-input"
import {
  orderingToSorting,
  toServerTableControls,
} from "@app/data-table/table-state"
import { useClampPage } from "@app/data-table/use-clamp-page"
import { Button } from "@app/ui/button"
import { messages } from "@app/core/constants/messages"
import {
  TransactionsFilterChips,
  TransactionsFilterPanel,
} from "./transaction-filters"
import { TransactionCard } from "./transaction-card"
import { TransactionsSortControl } from "./transactions-sort-control"
import { BulkCategoryDialog } from "./bulk-category-dialog"
import { DeleteTransactionsDialog } from "./delete-transactions-dialog"
import { TransactionFormDialog } from "./transaction-form-dialog"
import {
  EMPTY_TRANSACTIONS_FILTERS,
  TRANSACTIONS_PAGE_SIZE,
  hasActiveTransactionsFilters,
  toTransactionsQuery,
} from "./transactions-table-params"
import { useCategories } from "./use-categories"
import { useRefreshTransactionsOnSuccess } from "./use-invalidate-transactions"
import { useTransactionColumns } from "./use-transaction-columns"
import { useTransactionsTableState } from "./use-transactions-table-state"

/** The one dialog open, if any. `onDone` empties the table's selection after a bulk action. */
type OpenDialog =
  | { kind: "add" }
  | { kind: "edit"; transaction: TransactionResponse }
  | { kind: "delete"; ids: string[]; onDone?: () => void }
  | { kind: "recategorise"; ids: string[]; onDone: () => void }

export function TransactionsTable() {
  const state = useTransactionsTableState()
  const { categories, label } = useCategories()
  // Dialog state, not list state.
  const [dialog, setDialog] = useState<OpenDialog | null>(null)
  const closeDialog = (open: boolean) => !open && setDialog(null)
  // The refresh rides on the hook, so it runs even if the chip's menu is gone.
  const { mutate: updateTransaction } = useUpdateTransaction(
    useRefreshTransactionsOnSuccess(),
  )
  const onRecategorise = useCallback(
    (t: TransactionResponse, category: Category) =>
      updateTransaction({ transactionId: t.id, data: { category } }),
    [updateTransaction],
  )
  const onEdit = useCallback(
    (transaction: TransactionResponse) =>
      setDialog({ kind: "edit", transaction }),
    [],
  )
  const onDelete = useCallback(
    (t: TransactionResponse) => setDialog({ kind: "delete", ids: [t.id] }),
    [],
  )
  const columns = useTransactionColumns(label, {
    categories,
    onEdit,
    onDelete,
    onRecategorise,
  })
  const { data, isPending, isPlaceholderData, isError } = useListTransactions(
    toTransactionsQuery(state.query),
    {
      query: { placeholderData: keepPreviousData },
    },
  )
  const narrowed = hasActiveTransactionsFilters(state.query)

  const emptyPageOfMany = useClampPage(state, {
    pageSize: TRANSACTIONS_PAGE_SIZE,
    total: data?.total,
    rowCount: data?.items.length,
    isPlaceholderData,
  })

  const empty = narrowed ? (
    <div className="space-y-2">
      <p>No transactions match your filters.</p>
      <Button
        variant="outline"
        size="sm"
        onClick={() => {
          state.setSearch("")
          state.setFilters(EMPTY_TRANSACTIONS_FILTERS)
        }}
      >
        Clear filters
      </Button>
    </div>
  ) : (
    <div className="space-y-2">
      <p>No transactions yet.</p>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setDialog({ kind: "add" })}
      >
        Add a transaction
      </Button>
    </div>
  )

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-2xl font-semibold">Transactions</h1>
        <Button onClick={() => setDialog({ kind: "add" })}>
          <PlusIcon />
          Add transaction
        </Button>
      </div>
      <ServerDataTable<TransactionResponse, unknown>
        columns={columns}
        data={data?.items ?? []}
        controls={toServerTableControls(state, {
          pageSize: TRANSACTIONS_PAGE_SIZE,
          totalCount: data?.total ?? 0,
        })}
        isLoading={isPending || emptyPageOfMany}
        isPending={isPlaceholderData}
        errorMessage={
          isError && !data ? messages.toasts.genericError : undefined
        }
        noDataMessage={empty}
        enableRowSelection
        renderBulkActions={(selected, clear) => (
          <>
            <Button
              size="sm"
              onClick={() =>
                setDialog({
                  kind: "recategorise",
                  ids: selected.map((t) => t.id),
                  onDone: clear,
                })
              }
            >
              Recategorise
            </Button>
            <Button
              size="sm"
              variant="destructive"
              onClick={() =>
                setDialog({
                  kind: "delete",
                  ids: selected.map((t) => t.id),
                  onDone: clear,
                })
              }
            >
              <Trash2 />
              Delete
            </Button>
          </>
        )}
        headerActions={
          <TransactionsSortControl
            ordering={state.query.ordering}
            onChange={(ordering) => state.setSort(orderingToSorting(ordering))}
          />
        }
        renderCard={(row) => (
          <TransactionCard
            transaction={row.original}
            categoryLabel={label(row.original.category)}
            onEdit={() => onEdit(row.original)}
          />
        )}
        toolbar={
          <>
            <TableSearchInput
              value={state.search}
              onChange={state.setSearch}
              placeholder="Search merchants"
            />
            <TransactionsFilterPanel
              filters={state.filters}
              setFilters={state.setFilters}
              categories={categories}
            />
          </>
        }
        belowToolbar={
          <TransactionsFilterChips
            filters={state.filters}
            setFilters={state.setFilters}
            label={label}
          />
        }
      />
      {dialog?.kind === "add" && (
        <TransactionFormDialog mode="add" open onOpenChange={closeDialog} />
      )}
      {dialog?.kind === "edit" && (
        <TransactionFormDialog
          mode="edit"
          transaction={dialog.transaction}
          open
          onOpenChange={closeDialog}
        />
      )}
      {dialog?.kind === "delete" && (
        <DeleteTransactionsDialog
          ids={dialog.ids}
          open
          onOpenChange={closeDialog}
          onDeleted={dialog.onDone}
        />
      )}
      {dialog?.kind === "recategorise" && (
        <BulkCategoryDialog
          ids={dialog.ids}
          open
          onOpenChange={closeDialog}
          onDone={dialog.onDone}
        />
      )}
    </div>
  )
}
