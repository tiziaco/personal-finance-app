// apps/web/src/components/orders/orders-table-params.ts
// Illustrative: written against an invented `listOrders` route
// (GET /orders → OrderListResponse, `ordering: Literal[...]`, `search`, filters).
import {
  createLoader,
  compactQuery,
  dateMode,
  dateVal,
  DATE_FILTER_MODES,
  parseAsInteger,
  parseAsIsoDay,
  parseAsString,
  parseAsStringLiteral,
  toOffsetLimit,
  type DateFilterValue,
  type Values,
} from "@app/data-table/url-state/params"
import { EMPTY_DATE_FILTER } from "@app/data-table/url-state/date-filter"
import { ListOrdersOrdering, type ListOrdersParams } from "@app/api-client/types"

/** ≤ the route's `limit` cap. */
export const ORDERS_PAGE_SIZE = 20

export const ORDER_STATUSES = ["draft", "confirmed", "shipped", "cancelled"] as const
export type OrderStatus = (typeof ORDER_STATUSES)[number]
export const ORDER_STATUS_LABELS: Record<OrderStatus, string> = {
  draft: "Draft",
  confirmed: "Confirmed",
  shipped: "Shipped",
  cancelled: "Cancelled",
}

/** One parser set per API contract: every key here is forwarded by toOrdersQuery (except *_mode). */
export const ordersParsers = {
  page: parseAsInteger.withDefault(1),
  // The route's allow-list, from the generated const: an unknown field in a
  // hand-edited link parses to null instead of reaching the API.
  ordering: parseAsStringLiteral(Object.values(ListOrdersOrdering)),
  search: parseAsString.withDefault(""),
  status: parseAsStringLiteral(ORDER_STATUSES),
  customer_id: parseAsInteger,
  created_mode: parseAsStringLiteral(DATE_FILTER_MODES), // UI-only
  created_from: parseAsIsoDay,
  created_to: parseAsIsoDay,
}

// Tests parse a query string with it; the page itself never loads params.
export const loadOrdersTableParams = createLoader(ordersParsers)

type OrdersValues = Values<typeof ordersParsers>

/** The shape the panel and chips work with. */
export interface OrdersFilters {
  status: OrderStatus | null
  customer: number | null
  created: DateFilterValue
}

export const EMPTY_ORDERS_FILTERS: OrdersFilters = {
  status: null,
  customer: null,
  created: EMPTY_DATE_FILTER,
}

export function toOrdersFilters(v: OrdersValues): OrdersFilters {
  return {
    status: v.status,
    customer: v.customer_id,
    created: {
      mode: v.created_mode ?? dateMode(v.created_from, v.created_to),
      date1: v.created_from ?? "",
      date2: v.created_to ?? "",
    },
  }
}

export function fromOrdersFilters(f: OrdersFilters): Partial<OrdersValues> {
  return {
    status: f.status,
    customer_id: f.customer,
    created_mode: f.created.mode,
    created_from: dateVal(f.created, 1),
    created_to: dateVal(f.created, 2),
  }
}

/** API params for one page. Dates go through the filters shape so a hidden date never filters. */
export function toOrdersQuery(v: OrdersValues): ListOrdersParams {
  const { created } = toOrdersFilters(v)
  return compactQuery({
    ...toOffsetLimit(v.page, ORDERS_PAGE_SIZE),
    ordering: v.ordering,
    search: v.search,
    status: v.status,
    customer_id: v.customer_id,
    created_from: dateVal(created, 1),
    created_to: dateVal(created, 2),
  })
}
