import type { Dispatch, SetStateAction } from "react"
import type {
  OnChangeFn,
  PaginationState,
  SortingState,
} from "@tanstack/react-table"

/**
 * The list state every server-driven table reads and writes. Two hooks
 * produce it: useLocalTableState (React state) and useUrlTableState (the URL).
 * Tables, filter panels and chips only see this shape, so they work with
 * either. Loading state is not here: it belongs to the query.
 */
export interface DataTableState<TFilters> {
  filters: TFilters
  setFilters: Dispatch<SetStateAction<TFilters>>
  search: string
  setSearch: (value: string) => void
  /** 0-based */
  pageIndex: number
  setPage: (pageIndex: number) => void
  sorting: SortingState
  setSort: (sorting: SortingState) => void
}

/** What ServerDataTable needs, in TanStack's shape. Build it with toServerTableControls. */
export interface ServerTableControls {
  sorting: SortingState
  pagination: PaginationState
  totalCount: number
  onSortingChange: OnChangeFn<SortingState>
  onPaginationChange: OnChangeFn<PaginationState>
}

/** Plain function, not a hook: it holds no state, the state hook does. */
export function toServerTableControls(
  state: Pick<
    DataTableState<unknown>,
    "sorting" | "pageIndex" | "setPage" | "setSort"
  >,
  { pageSize, totalCount }: { pageSize: number; totalCount: number },
): ServerTableControls {
  const pagination: PaginationState = { pageIndex: state.pageIndex, pageSize }
  return {
    sorting: state.sorting,
    pagination,
    totalCount,
    onSortingChange: (updater) =>
      state.setSort(
        typeof updater === "function" ? updater(state.sorting) : updater,
      ),
    onPaginationChange: (updater) => {
      const next = typeof updater === "function" ? updater(pagination) : updater
      state.setPage(next.pageIndex)
    },
  }
}

/** API `ordering` ("-created_at") → TanStack sorting. */
export function orderingToSorting(
  ordering: string | null | undefined,
): SortingState {
  if (!ordering) return []
  return [{ id: ordering.replace(/^-/, ""), desc: ordering.startsWith("-") }]
}

/** TanStack sorting → API `ordering`. Single-column sort only. */
export function sortingToOrdering(sorting: SortingState): string | null {
  const first = sorting[0]
  return first ? `${first.desc ? "-" : ""}${first.id}` : null
}
