// apps/web/src/components/items/add-items-dialog.tsx
// Illustrative: an invented `listItems` route (offset/limit, ordering, search,
// status). A table inside a dialog keeps its state local: paging in the URL
// would make Back page the table instead of closing the dialog.
"use client"

import { keepPreviousData } from "@tanstack/react-query"
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@app/ui/dialog"
import { ServerDataTable } from "@app/data-table/server-data-table"
import { TableSearchInput } from "@app/data-table/table-search-input"
import { toListQuery } from "@app/data-table/list-query"
import { toServerTableControls } from "@app/data-table/table-state"
import { useLocalTableState } from "@app/data-table/use-local-table-state"
import { FilterSelect } from "@app/data-table/filters/filter-panel"
import { useListItems } from "@app/api-client/endpoints/items"
import type { ItemResponse, ListItemsParams } from "@app/api-client/types"
import { messages } from "@app/core/constants/messages"
import { useItemColumns } from "./use-item-columns"

const ITEMS_PAGE_SIZE = 10 // ≤ the route's limit cap

type ItemFilters = { status: "active" | "archived" | null }

export function AddItemsDialog({
  open,
  onOpenChange,
  onAdd,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onAdd: (item: ItemResponse) => void
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-3xl">
        <DialogHeader>
          <DialogTitle>Add items</DialogTitle>
        </DialogHeader>
        {/* The popup unmounts when closed, so the picker's state resets on every open
            and nothing fetches while it is closed. */}
        <AddItemsPicker onAdd={onAdd} />
      </DialogContent>
    </Dialog>
  )
}

function AddItemsPicker({ onAdd }: { onAdd: (item: ItemResponse) => void }) {
  const state = useLocalTableState<ItemFilters>({ initialFilters: { status: null } })
  const { data, isPending, isPlaceholderData, isError } = useListItems(
    // Sortable column ids are the route's ordering allow-list, so the string
    // the table produces is one of ListItemsParams["ordering"].
    toListQuery(state.query, ITEMS_PAGE_SIZE) as ListItemsParams,
    { query: { placeholderData: keepPreviousData } },
  )
  const columns = useItemColumns({ onAdd })

  return (
    <ServerDataTable
      columns={columns}
      data={data?.items ?? []}
      controls={toServerTableControls(state, {
        pageSize: ITEMS_PAGE_SIZE,
        totalCount: data?.total ?? 0,
      })}
      isLoading={isPending}
      isPending={isPlaceholderData}
      errorMessage={isError && !data ? messages.toasts.genericError : undefined}
      noDataMessage="No items match."
      toolbar={
        <>
          <TableSearchInput
            value={state.search}
            onChange={state.setSearch}
            placeholder="Search items"
          />
          <FilterSelect
            aria-label="Status"
            className="w-40"
            value={state.filters.status ?? ""}
            onChange={(e) => {
              const status = (e.target.value || null) as ItemFilters["status"]
              state.setFilters((f) => ({ ...f, status }))
            }}
          >
            <option value="">Any status</option>
            <option value="active">Active</option>
            <option value="archived">Archived</option>
          </FilterSelect>
        </>
      }
    />
  )
}
