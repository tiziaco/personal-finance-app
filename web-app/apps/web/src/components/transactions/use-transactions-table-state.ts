import { createUrlTableStateHook } from "@app/data-table/url-state/use-url-table-state"
import {
  fromTransactionsFilters,
  toTransactionsFilters,
  transactionsParsers,
} from "./transactions-table-params"

export const useTransactionsTableState = createUrlTableStateHook({
  parsers: transactionsParsers,
  toFilters: toTransactionsFilters,
  fromFilters: fromTransactionsFilters,
})
