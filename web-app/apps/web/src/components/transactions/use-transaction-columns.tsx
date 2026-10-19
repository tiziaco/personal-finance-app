"use client"

import { useMemo } from "react"
import { MoreHorizontalIcon, PencilIcon, Trash2Icon } from "lucide-react"
import type { ColumnDef } from "@app/data-table/columns"
import type {
  Category,
  CategoryResponse,
  TransactionResponse,
} from "@app/api-client/types"
import { Button } from "@app/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@app/ui/dropdown-menu"
import { CategoryPicker } from "./category-picker"
import {
  transactionAmountClass,
  formatSignedAmount,
  formatDate,
  isLowConfidence,
} from "./format"
import { CategoryTile } from "./category-icon"

export type TransactionRowActions = {
  categories: CategoryResponse[]
  onEdit: (transaction: TransactionResponse) => void
  onDelete: (transaction: TransactionResponse) => void
  onRecategorise: (transaction: TransactionResponse, category: Category) => void
}

// Sortable ids are ListTransactionsOrdering fields (date, amount, merchant).
export function useTransactionColumns(
  label: (slug: string) => string,
  { categories, onEdit, onDelete, onRecategorise }: TransactionRowActions,
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
      {
        accessorKey: "merchant",
        id: "merchant",
        header: "Merchant",
        cell: ({ row }) => (
          <div className="flex items-center gap-3">
            <CategoryTile slug={row.original.category} size="sm" />
            <span className="min-w-0 truncate">{row.original.merchant}</span>
          </div>
        ),
      },
      {
        accessorKey: "amount",
        id: "amount",
        header: "Amount",
        meta: { align: "right", width: "8rem" },
        cell: ({ row }) => (
          <span className={transactionAmountClass(row.original.amount)}>
            {formatSignedAmount(row.original.amount)}
          </span>
        ),
      },
      {
        id: "category",
        header: "Category",
        enableSorting: false,
        cell: ({ row }) => (
          <CategoryPicker
            value={row.original.category}
            categories={categories}
            label={label}
            onChange={(category) => onRecategorise(row.original, category)}
          />
        ),
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
              className={
                isLowConfidence(c)
                  ? "text-(--warning-text)"
                  : "text-muted-foreground"
              }
            >
              {`${Math.round(c * 100)}%`}
            </span>
          )
        },
      },
      {
        id: "actions",
        header: "",
        enableSorting: false,
        enableHiding: false,
        meta: { width: "3rem" },
        cell: ({ row }) => (
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label="Row actions"
                />
              }
            >
              <MoreHorizontalIcon />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-auto">
              <DropdownMenuItem onClick={() => onEdit(row.original)}>
                <PencilIcon />
                Edit
              </DropdownMenuItem>
              <DropdownMenuItem
                variant="destructive"
                onClick={() => onDelete(row.original)}
              >
                <Trash2Icon />
                Delete
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        ),
      },
    ],
    [label, categories, onEdit, onDelete, onRecategorise],
  )
}
