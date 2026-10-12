// apps/web/src/components/orders/orders-table.tsx
"use client"

import { keepPreviousData } from "@tanstack/react-query"
import { useListCustomers } from "@app/api-client/endpoints/customers"
import { useListOrders } from "@app/api-client/endpoints/orders"
import { ServerDataTable } from "@app/data-table/server-data-table"
import { TableSearchInput } from "@app/data-table/table-search-input"
import { toServerTableControls } from "@app/data-table/table-state"
import { messages } from "@app/core/constants/messages"
import { OrdersFilterChips, OrdersFilterPanel } from "./orders-filters"
import { ORDERS_PAGE_SIZE, toOrdersQuery } from "./orders-table-params"
import { useOrderColumns } from "./use-order-columns"
import { useOrdersTableState } from "./use-orders-table-state"

// All list state comes from the URL through one hook call; the rows come from
// the generated hook keyed on its `query`. Nothing is mirrored in useState.
export function OrdersTable() {
  const state = useOrdersTableState()
  const columns = useOrderColumns()
  const { data, isPending, isPlaceholderData, isError } = useListOrders(
    toOrdersQuery(state.query),
    { query: { placeholderData: keepPreviousData } },
  )
  // Filter options are their own query, not part of the list response.
  const customers = useListCustomers({ limit: 100 }).data?.items ?? []

  return (
    <ServerDataTable
      columns={columns}
      data={data?.items ?? []}
      controls={toServerTableControls(state, {
        pageSize: ORDERS_PAGE_SIZE,
        totalCount: data?.total ?? 0,
      })}
      isLoading={isPending}
      isPending={isPlaceholderData}
      // QueryProvider has already toasted; this only replaces the empty state.
      errorMessage={isError && !data ? messages.toasts.genericError : undefined}
      noDataMessage="No orders match these filters."
      toolbar={
        <>
          <TableSearchInput
            value={state.search}
            onChange={state.setSearch}
            placeholder="Search orders"
          />
          <OrdersFilterPanel
            customers={customers}
            filters={state.filters}
            setFilters={state.setFilters}
          />
        </>
      }
      belowToolbar={
        <OrdersFilterChips
          customers={customers}
          filters={state.filters}
          setFilters={state.setFilters}
        />
      }
    />
  )
}
