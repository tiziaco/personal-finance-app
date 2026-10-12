// apps/web/src/components/orders/use-order-columns.tsx
"use client"

import { useMemo } from "react"
import type { ColumnDef } from "@app/data-table/columns"
import type { OrderResponse } from "@app/api-client/types"
import { ORDER_STATUS_LABELS } from "./orders-table-params"

const money = new Intl.NumberFormat(undefined, { style: "currency", currency: "EUR" })

// Sortable ids are ListOrdersOrdering fields (number, created_at, total);
// every other column says enableSorting: false.
export function useOrderColumns(): ColumnDef<OrderResponse>[] {
  return useMemo<ColumnDef<OrderResponse>[]>(
    () => [
      { accessorKey: "number", id: "number", header: "Order" },
      {
        accessorKey: "customer_name",
        id: "customer_name",
        header: "Customer",
        enableSorting: false,
      },
      {
        accessorKey: "status",
        id: "status",
        header: "Status",
        enableSorting: false,
        cell: ({ row }) => ORDER_STATUS_LABELS[row.original.status],
      },
      { accessorKey: "created_at", id: "created_at", header: "Created" },
      {
        accessorKey: "total",
        id: "total",
        header: "Total",
        meta: { align: "right" },
        cell: ({ getValue }) => money.format(getValue<number>()),
      },
    ],
    [],
  )
}
