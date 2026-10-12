// apps/web/src/components/orders/use-orders-table-state.ts
import { createUrlTableStateHook } from "@app/data-table/url-state/use-url-table-state"
import { fromOrdersFilters, ordersParsers, toOrdersFilters } from "./orders-table-params"

export const useOrdersTableState = createUrlTableStateHook({
  parsers: ordersParsers,
  toFilters: toOrdersFilters,
  fromFilters: fromOrdersFilters,
})
