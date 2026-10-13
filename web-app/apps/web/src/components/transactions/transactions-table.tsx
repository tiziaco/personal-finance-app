"use client"

import { keepPreviousData } from "@tanstack/react-query"
import { useListTransactions } from "@app/api-client/endpoints/transactions"
import type { TransactionResponse } from "@app/api-client/types"
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
import {
  EMPTY_TRANSACTIONS_FILTERS,
  TRANSACTIONS_PAGE_SIZE,
  hasActiveTransactionsFilters,
  toTransactionsQuery,
} from "./transactions-table-params"
import { useCategories } from "./use-categories"
import { useTransactionColumns } from "./use-transaction-columns"
import { useTransactionsTableState } from "./use-transactions-table-state"

export function TransactionsTable() {
  const state = useTransactionsTableState()
  const { categories, label } = useCategories()
  const columns = useTransactionColumns(label)
  const { data, isPending, isPlaceholderData, isError } = useListTransactions(
    toTransactionsQuery(state.query),
    {
      query: { placeholderData: keepPreviousData },
    },
  )
  const narrowed = hasActiveTransactionsFilters(state.query)

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
    <p>No transactions yet.</p>
  )

  return (
    <ServerDataTable<TransactionResponse, unknown>
      columns={columns}
      data={data?.items ?? []}
      controls={toServerTableControls(state, {
        pageSize: TRANSACTIONS_PAGE_SIZE,
        totalCount: data?.total ?? 0,
      })}
      isLoading={isPending}
      isPending={isPlaceholderData}
      errorMessage={isError && !data ? messages.toasts.genericError : undefined}
      noDataMessage={empty}
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
  )
}
