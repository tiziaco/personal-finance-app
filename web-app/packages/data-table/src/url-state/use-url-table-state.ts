"use client"

import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react"
import {
  debounce,
  useQueryStates,
  type Options,
  type UseQueryStatesKeysMap,
  type Values,
} from "nuqs"
import type { SortingState } from "@tanstack/react-table"
import {
  orderingToSorting,
  sortingToOrdering,
  type DataTableState,
} from "../table/table-state"

export const SEARCH_DEBOUNCE_MS = 300

/** Every list parser set has these three keys. */
type ListKeyMap = UseQueryStatesKeysMap & {
  page: unknown
  ordering: unknown
  search: unknown
}
type UrlKeys<KeyMap> = Partial<Record<keyof KeyMap, string>>

/**
 * `values`, holding back a typed search until the user pauses. nuqs updates
 * `values.search` on every keystroke (only the URL write is debounced), and
 * the query key must not follow it. Clearing the search is not held back.
 */
function useSettledValues<V extends { search: unknown }>(values: V): V {
  const search = values.search as string
  const [settledSearch, setSettledSearch] = useState(search)
  const [held, setHeld] = useState(values)
  const typing = search !== "" && search !== settledSearch

  // Adjusted while rendering, not in an effect, so `query` never lags a
  // filter or page change by a render.
  if (!typing && held !== values) setHeld(values)
  if (search === "" && settledSearch !== "") setSettledSearch("")

  // Keyed on the string: nuqs hands back a new `values` object when the
  // debounced URL write lands, which must not restart the wait.
  useEffect(() => {
    if (!typing) return
    const id = setTimeout(() => setSettledSearch(search), SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(id)
  }, [typing, search])

  return typing ? held : values
}

/**
 * URL-as-the-only-copy list state. Values are read from the URL on every
 * render, so Back/Forward can't leave a control showing stale state.
 *
 * - `shallow: true`: a write changes the URL only. The rows come from the
 *   caller's generated hook, keyed on `query`.
 * - Filter, search and sort changes reset page. Page, sort and filter writes
 *   push history by default; typed search replaces it, debounced.
 */
export function useUrlTableState<KeyMap extends ListKeyMap>(
  parsers: KeyMap,
  { urlKeys }: { urlKeys?: UrlKeys<KeyMap> } = {},
) {
  const [values, setValues] = useQueryStates(parsers, {
    shallow: true,
    urlKeys,
  })
  const query = useSettledValues(values)

  // Setters are stable (useCallback) so callers can use them in deps.
  const setFilters = useCallback(
    (patch: Partial<Values<KeyMap>>, options?: Options) =>
      setValues({ ...patch, page: null } as Partial<Values<KeyMap>>, {
        history: "push",
        ...options,
      }),
    [setValues],
  )

  const setPage = useCallback(
    (pageIndex: number) =>
      setValues(
        {
          page: pageIndex <= 0 ? null : pageIndex + 1,
        } as Partial<Values<KeyMap>>,
        { history: "push" },
      ),
    [setValues],
  )

  const setSort = useCallback(
    (next: SortingState) =>
      setFilters({ ordering: sortingToOrdering(next) } as Partial<
        Values<KeyMap>
      >),
    [setFilters],
  )

  // Debounce at the setter, never on the parser. Clearing applies at once so
  // the full list comes back.
  const setSearch = useCallback(
    (value: string) =>
      setFilters({ search: value } as Partial<Values<KeyMap>>, {
        history: "replace",
        limitUrlUpdates:
          value === "" ? undefined : debounce(SEARCH_DEBOUNCE_MS),
      }),
    [setFilters],
  )

  // Page and sort follow `query`, so the pager and headers match the rows.
  const ordering = query.ordering as string | null
  const sorting = useMemo(() => orderingToSorting(ordering), [ordering])

  return {
    values,
    setValues,
    setFilters,
    /** what to fetch with: pass to the list's to<Domain>Query */
    query,
    pageIndex: Math.max(0, (query.page as number) - 1),
    sorting,
    search: values.search as string,
    setPage,
    setSort,
    setSearch,
  }
}

export interface UrlTableState<
  KeyMap extends UseQueryStatesKeysMap,
  TFilters,
> extends DataTableState<TFilters> {
  /** the parsed URL, search debounced: pass to the list's to<Domain>Query */
  query: Values<KeyMap>
}

/**
 * Binds a parser set and its mappers into a per-list hook:
 *   export const useOrdersTableState = createUrlTableStateHook({ parsers, toFilters, fromFilters })
 */
export function createUrlTableStateHook<
  KeyMap extends ListKeyMap,
  TFilters,
>(config: {
  parsers: KeyMap
  urlKeys?: UrlKeys<KeyMap>
  toFilters: (values: Values<KeyMap>) => TFilters
  fromFilters: (filters: TFilters) => Partial<Values<KeyMap>>
}) {
  return function useTableState(): UrlTableState<KeyMap, TFilters> {
    const url = useUrlTableState(config.parsers, { urlKeys: config.urlKeys })
    const { setValues, setFilters: setUrlFilters, values } = url

    // `config` is module-level, so it stays out of the deps.
    const setFilters: Dispatch<SetStateAction<TFilters>> = useCallback(
      (update) => {
        if (typeof update === "function") {
          // Compose inside nuqs's own updater so a functional update reads the
          // latest queued values; otherwise back-to-back writes clobber each other.
          return setValues(
            (prev) =>
              ({
                ...config.fromFilters(
                  (update as (prev: TFilters) => TFilters)(
                    config.toFilters(prev),
                  ),
                ),
                page: null,
              }) as Partial<Values<KeyMap>>,
            { history: "push" },
          )
        }
        // The returned promise lets tests await the URL flush; the declared type stays void.
        return setUrlFilters(config.fromFilters(update))
      },
      [setValues, setUrlFilters],
    )

    const filters = useMemo(() => config.toFilters(values), [values])

    return {
      filters,
      setFilters,
      search: url.search,
      setSearch: url.setSearch,
      pageIndex: url.pageIndex,
      setPage: url.setPage,
      sorting: url.sorting,
      setSort: url.setSort,
      query: url.query,
    }
  }
}
