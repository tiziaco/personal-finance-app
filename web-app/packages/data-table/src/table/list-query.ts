/** Every key optional, with null/undefined removed from each value type. */
export type Defined<T> = { [K in keyof T]?: Exclude<T[K], null | undefined> }

/**
 * Drops keys whose value is null, undefined or "", so an unset filter is absent
 * from the request instead of sent empty. 0 and false are kept: they're real
 * selections. Generated query types are all-optional, which is what makes the
 * result assignable to them.
 */
export const compactQuery = <T extends object>(query: T): Defined<T> =>
  Object.fromEntries(
    Object.entries(query).filter(([, value]) => value != null && value !== ""),
  ) as Defined<T>

/** 1-based page → the API's offset/limit. */
export const toOffsetLimit = (page: number, pageSize: number) => ({
  offset: (Math.max(1, page) - 1) * pageSize,
  limit: pageSize,
})

/** The query a local-state server table fetches with. `search` is already debounced. */
export interface ListQuery<TFilters> {
  /** 1-based */
  page: number
  ordering: string | null
  search: string
  filters: TFilters
}

/**
 * Flat API params for one page: offset/limit, ordering, search and the
 * filters spread as-is. If the API names or shapes filters differently, map
 * `query.filters` yourself and wrap the result in compactQuery.
 */
export function toListQuery<TFilters extends object>(
  query: ListQuery<TFilters>,
  pageSize: number,
) {
  return compactQuery({
    ...query.filters,
    ...toOffsetLimit(query.page, pageSize),
    ordering: query.ordering,
    search: query.search,
  })
}
