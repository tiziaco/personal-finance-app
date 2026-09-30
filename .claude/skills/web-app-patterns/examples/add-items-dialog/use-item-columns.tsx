// apps/internal-portal/src/components/items/use-item-columns.tsx
"use client"

import { useMemo } from "react"
import { Button } from "@app/ui/button"
import type { ColumnDef } from "@app/data-table/columns"
import type { ItemResponse } from "@app/api-client/types"

// Sortable ids are the route's ordering fields (name, sku); the rest opt out.
export function useItemColumns({
  onAdd,
}: {
  onAdd: (item: ItemResponse) => void
}): ColumnDef<ItemResponse>[] {
  return useMemo<ColumnDef<ItemResponse>[]>(
    () => [
      { accessorKey: "name", id: "name", header: "Name" },
      { accessorKey: "sku", id: "sku", header: "SKU" },
      { accessorKey: "status", id: "status", header: "Status", enableSorting: false },
      {
        id: "add",
        header: "",
        enableSorting: false,
        meta: { align: "right" },
        cell: ({ row }) => (
          <Button size="sm" variant="outline" onClick={() => onAdd(row.original)}>
            Add
          </Button>
        ),
      },
    ],
    [onAdd],
  )
}
