"use client"

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type SetStateAction,
} from "react"
import type { SortingState } from "@tanstack/react-table"
import type { ListQuery } from "./list-query"
import {
  orderingToSorting,
  sortingToOrdering,
  type DataTableState,
} from "./table-state"

export interface LocalTableState<TFilters> extends DataTableState<TFilters> {
  /** what to fetch with: pass to toListQuery. `search` here is debounced. */
  query: ListQuery<TFilters>
}

/**
 * List state kept in React state, for server tables that must not use the
 * URL: inside dialogs, drawers, popovers, secondary panels. Any filter, search
 * or sort change resets to page 1.
 */
export function useLocalTableState<TFilters>({
  initialFilters,
  initialOrdering = null,
  searchDebounceMs = 300,
}: {
  initialFilters: TFilters
  initialOrdering?: string | null
  searchDebounceMs?: number
}): LocalTableState<TFilters> {
  const [filters, setFiltersState] = useState<TFilters>(initialFilters)
  const [ordering, setOrdering] = useState<string | null>(initialOrdering)
  const [page, setPageState] = useState(1)
  const [search, setSearchState] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")

  useEffect(() => {
    if (search === "") return
    const id = setTimeout(() => {
      setDebouncedSearch(search)
      setPageState(1)
    }, searchDebounceMs)
    return () => clearTimeout(id)
  }, [search, searchDebounceMs])

  // Stable setters, so callers can pass them to memoised children and effect deps.
  const setFilters = useCallback((update: SetStateAction<TFilters>) => {
    setFiltersState(update)
    setPageState(1)
  }, [])

  const setSort = useCallback((next: SortingState) => {
    setOrdering(sortingToOrdering(next))
    setPageState(1)
  }, [])

  const setPage = useCallback(
    (pageIndex: number) => setPageState(Math.max(0, pageIndex) + 1),
    [],
  )

  const setSearch = useCallback((value: string) => {
    setSearchState(value)
    // Clearing applies at once so the full list comes back without a delay.
    if (value === "") {
      setDebouncedSearch("")
      setPageState(1)
    }
  }, [])

  const sorting = useMemo(() => orderingToSorting(ordering), [ordering])

  return {
    filters,
    setFilters,
    search,
    setSearch,
    pageIndex: page - 1,
    setPage,
    sorting,
    setSort,
    query: { page, ordering, search: debouncedSearch, filters },
  }
}
