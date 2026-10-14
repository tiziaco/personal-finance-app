import {
  createLoader,
  compactQuery,
  dateMode,
  dateVal,
  DATE_FILTER_MODES,
  parseAsArrayOf,
  parseAsBoolean,
  parseAsInteger,
  parseAsIsoDay,
  parseAsString,
  parseAsStringLiteral,
  toOffsetLimit,
  type DateFilterValue,
  type Values,
} from "@app/data-table/url-state/params"
import {
  EMPTY_DATE_FILTER,
  isDateFilterActive,
} from "@app/data-table/url-state/date-filter"
import {
  Category,
  ListTransactionsOrdering,
  type ListTransactionsParams,
} from "@app/api-client/types"

/** ≤ the route's `limit` cap (100). */
export const TRANSACTIONS_PAGE_SIZE = 20

/** One parser set per API contract: every key is forwarded by toTransactionsQuery (except date_mode). */
export const transactionsParsers = {
  page: parseAsInteger.withDefault(1),
  ordering: parseAsStringLiteral(Object.values(ListTransactionsOrdering)),
  search: parseAsString.withDefault(""),
  category: parseAsArrayOf(
    parseAsStringLiteral(Object.values(Category)),
  ).withDefault([]),
  amount_min: parseAsString,
  amount_max: parseAsString,
  is_recurring: parseAsBoolean,
  date_mode: parseAsStringLiteral(DATE_FILTER_MODES), // UI-only
  date_from: parseAsIsoDay,
  date_to: parseAsIsoDay,
}

export const loadTransactionsTableParams = createLoader(transactionsParsers)

type TransactionsValues = Values<typeof transactionsParsers>

export interface TransactionsFilters {
  categories: Category[]
  amountMin: string | null
  amountMax: string | null
  recurring: boolean | null
  date: DateFilterValue
}

export const EMPTY_TRANSACTIONS_FILTERS: TransactionsFilters = {
  categories: [],
  amountMin: null,
  amountMax: null,
  recurring: null,
  date: EMPTY_DATE_FILTER,
}

export function toTransactionsFilters(
  v: TransactionsValues,
): TransactionsFilters {
  return {
    categories: v.category,
    amountMin: v.amount_min,
    amountMax: v.amount_max,
    recurring: v.is_recurring,
    date: {
      mode: v.date_mode ?? dateMode(v.date_from, v.date_to),
      date1: v.date_from ?? "",
      date2: v.date_to ?? "",
    },
  }
}

export function fromTransactionsFilters(
  f: TransactionsFilters,
): Partial<TransactionsValues> {
  return {
    // nuqs drops an empty array from the URL
    category: f.categories,
    amount_min: f.amountMin || null,
    amount_max: f.amountMax || null,
    is_recurring: f.recurring,
    date_mode: f.date.mode,
    date_from: dateVal(f.date, 1),
    date_to: dateVal(f.date, 2),
  }
}

export function toTransactionsQuery(
  v: TransactionsValues,
): ListTransactionsParams {
  const { date } = toTransactionsFilters(v)
  return compactQuery({
    ...toOffsetLimit(v.page, TRANSACTIONS_PAGE_SIZE),
    ordering: v.ordering,
    // The route caps search at 100; trimmed, so "rewe " matches like "rewe".
    search: v.search.trim().slice(0, 100),
    category: v.category.length > 0 ? v.category : undefined,
    amount_min: v.amount_min,
    amount_max: v.amount_max,
    is_recurring: v.is_recurring,
    date_from: dateVal(date, 1),
    date_to: dateVal(date, 2),
  })
}

/** Any filter or search narrows the list: the empty state then offers to clear them. */
export function hasActiveTransactionsFilters(v: TransactionsValues): boolean {
  const f = toTransactionsFilters(v)
  return (
    v.search.trim() !== "" ||
    f.categories.length > 0 ||
    f.amountMin != null ||
    f.amountMax != null ||
    f.recurring != null ||
    isDateFilterActive(f.date)
  )
}
