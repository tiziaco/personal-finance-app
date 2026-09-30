// apps/internal-portal/src/components/products/products-table.tsx
// Illustrative: an invented `listProducts` route returning every product (a
// small, bounded catalogue), so sorting, search and paging run in memory.
"use client"

import { ClientDataTable } from "@app/data-table/client-data-table"
import { useStoredColumnVisibility } from "@app/data-table/use-stored-column-visibility"
import { useListProducts } from "@app/api-client/endpoints/products"
import type { ProductResponse } from "@app/api-client/types"
import { useProductColumns } from "./use-product-columns"

// A module constant: the hook memoises on this reference.
const DEFAULT_VISIBILITY = { sku: false }

export function ProductsTable({
  canEdit,
  onEdit,
}: {
  canEdit: boolean
  onEdit: (product: ProductResponse) => void // stable: the caller's useCallback
}) {
  const { data, isPending } = useListProducts()
  const columns = useProductColumns({ canEdit, onEdit })
  const visibility = useStoredColumnVisibility("products", DEFAULT_VISIBILITY)

  return (
    <ClientDataTable
      columns={columns}
      data={data?.items ?? []}
      isLoading={isPending}
      searchable
      searchPlaceholder="Search products"
      pageSize={20}
      showColumnToggle
      {...visibility}
      noDataMessage="No products yet."
    />
  )
}
