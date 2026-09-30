// apps/internal-portal/src/components/products/use-product-columns.tsx
"use client"

import { useMemo } from "react"
import { Pencil } from "lucide-react"
import { Button } from "@app/ui/button"
import type { ColumnDef } from "@app/data-table/columns"
import type { ProductResponse } from "@app/api-client/types"

const money = new Intl.NumberFormat(undefined, { style: "currency", currency: "EUR" })

// Parameters == useMemo deps. Pass narrowed values (canEdit, not the user) and
// stable callbacks. A client table sorts in memory, so any column may sort.
export function useProductColumns({
  canEdit,
  onEdit,
}: {
  canEdit: boolean
  onEdit: (product: ProductResponse) => void
}): ColumnDef<ProductResponse>[] {
  return useMemo<ColumnDef<ProductResponse>[]>(
    () => [
      { accessorKey: "name", header: "Name" },
      { accessorKey: "sku", header: "SKU", meta: { width: "8rem" } },
      {
        accessorKey: "price",
        header: "Price",
        meta: { align: "right" },
        cell: ({ getValue }) => money.format(getValue<number>()),
      },
      { accessorKey: "stock", header: "Stock", meta: { align: "right" } },
      {
        id: "actions",
        header: "",
        enableSorting: false,
        enableHiding: false,
        meta: { width: "3rem" },
        cell: ({ row }) =>
          canEdit ? (
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={`Edit ${row.original.name}`}
              onClick={() => onEdit(row.original)}
            >
              <Pencil />
            </Button>
          ) : null,
      },
    ],
    [canEdit, onEdit],
  )
}
