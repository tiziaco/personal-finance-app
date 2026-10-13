"use client"

import { useCallback, useEffect, useState } from "react"
import { PlusIcon } from "lucide-react"
import { keepPreviousData } from "@tanstack/react-query"
import {
  useListTransactions,
  useUpdateTransaction,
} from "@app/api-client/endpoints/transactions"
import type { Category, TransactionResponse } from "@app/api-client/types"
import { ServerDataTable } from "@app/data-table/server-data-table"
import { TableSearchInput } from "@app/data-table/table-search-input"
import { toServerTableControls } from "@app/data-table/table-state"
import { Button } from "@app/ui/button"
import { messages } from "@app/core/constants/messages"
import {
  TransactionsFilterChips,
  TransactionsFilterPanel,
} from "./transaction-filters"
import { TransactionCard } from "./transaction-card"
import { DeleteTransactionsDialog } from "./delete-transactions-dialog"
import { TransactionFormDialog } from "./transaction-form-dialog"
import {
  EMPTY_TRANSACTIONS_FILTERS,
  TRANSACTIONS_PAGE_SIZE,
  hasActiveTransactionsFilters,
  toTransactionsQuery,
} from "./transactions-table-params"
import { useCategories } from "./use-categories"
import { useInvalidateTransactions } from "./use-invalidate-transactions"
import { useTransactionColumns } from "./use-transaction-columns"
import { useTransactionsTableState } from "./use-transactions-table-state"

export function TransactionsTable() {
  const state = useTransactionsTableState()
  const { categories, label } = useCategories()
  // Which dialog is open: dialog state, not list state.
  const [editing, setEditing] = useState<TransactionResponse | "new" | null>(
    null,
  )
  const [deleting, setDeleting] = useState<string[] | null>(null)
  const invalidate = useInvalidateTransactions()
  const { mutate: updateTransaction } = useUpdateTransaction()
  const onRecategorise = useCallback(
    (t: TransactionResponse, category: Category) =>
      updateTransaction(
        { transactionId: t.id, data: { category } },
        { onSuccess: () => invalidate() },
      ),
    [updateTransaction, invalidate],
  )
  const onDelete = useCallback(
    (t: TransactionResponse) => setDeleting([t.id]),
    [],
  )
  const columns = useTransactionColumns(label, {
    categories,
    onEdit: setEditing,
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

  // A page past the end — its last row deleted, or a hand-edited ?page= —
  // comes back empty with the real total. Neither empty state is true then:
  // show the skeleton and move to the last page that has rows, without a
  // Back entry. Only a page beyond that one moves, so this cannot loop.
  const total = data?.total ?? 0
  const lastPageIndex = Math.ceil(total / TRANSACTIONS_PAGE_SIZE) - 1
  const emptyPageOfMany =
    !isPlaceholderData && data?.items.length === 0 && total > 0
  const pastTheEnd = emptyPageOfMany && state.pageIndex > lastPageIndex
  const { setPage } = state
  useEffect(() => {
    if (pastTheEnd) setPage(lastPageIndex, { history: "replace" })
  }, [pastTheEnd, lastPageIndex, setPage])

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
      <Button variant="outline" size="sm" onClick={() => setEditing("new")}>
        Add a transaction
      </Button>
    </div>
  )

  return (
    <>
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
        headerActions={
          <Button size="sm" onClick={() => setEditing("new")}>
            <PlusIcon />
            Add transaction
          </Button>
        }
        renderCard={(row) => (
          <TransactionCard
            transaction={row.original}
            categoryLabel={label(row.original.category)}
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
      {editing &&
        (editing === "new" ? (
          <TransactionFormDialog
            mode="add"
            open
            onOpenChange={(open) => !open && setEditing(null)}
          />
        ) : (
          <TransactionFormDialog
            mode="edit"
            transaction={editing}
            open
            onOpenChange={(open) => !open && setEditing(null)}
          />
        ))}
      {deleting && (
        <DeleteTransactionsDialog
          ids={deleting}
          open
          onOpenChange={(open) => !open && setDeleting(null)}
        />
      )}
    </>
  )
}
