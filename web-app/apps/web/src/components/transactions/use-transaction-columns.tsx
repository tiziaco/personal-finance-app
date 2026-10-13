"use client"

import { useMemo } from "react"
import type { ColumnDef } from "@app/data-table/columns"
import type { TransactionResponse } from "@app/api-client/types"
import { cn } from "@app/core/lib/utils"
import { formatAmount, formatDate, isExpense, isLowConfidence } from "./format"

// Sortable ids are ListTransactionsOrdering fields (date, amount, merchant).
export function useTransactionColumns(
  label: (slug: string) => string,
): ColumnDef<TransactionResponse>[] {
  return useMemo<ColumnDef<TransactionResponse>[]>(
    () => [
      {
        accessorKey: "date",
        id: "date",
        header: "Date",
        meta: { width: "8rem" },
        cell: ({ row }) => formatDate(row.original.date),
      },
      { accessorKey: "merchant", id: "merchant", header: "Merchant" },
      {
        accessorKey: "amount",
        id: "amount",
        header: "Amount",
        meta: { align: "right", width: "8rem" },
        cell: ({ row }) => (
          <span
            className={
              isExpense(row.original.amount)
                ? "text-destructive"
                : "text-emerald-600 dark:text-emerald-400"
            }
          >
            {formatAmount(row.original.amount)}
          </span>
        ),
      },
      {
        id: "category",
        header: "Category",
        enableSorting: false,
        cell: ({ row }) => label(row.original.category),
      },
      {
        id: "confidence",
        header: "Confidence",
        enableSorting: false,
        meta: { align: "right", width: "6rem" },
        cell: ({ row }) => {
          const c = row.original.confidence
          return (
            <span
              className={cn(
                isLowConfidence(c)
                  ? "text-amber-600 dark:text-amber-400"
                  : "text-muted-foreground",
              )}
            >
              {`${Math.round(c * 100)}%`}
            </span>
          )
        },
      },
    ],
    [label],
  )
}
