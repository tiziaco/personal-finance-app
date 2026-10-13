"use client"

import type { ListTransactionsOrdering } from "@app/api-client/types"
import { FilterSelect } from "@app/data-table/filters/filter-panel"

/** The orderings a phone offers, in menu order. The first is the list's default. */
const SORT_OPTIONS: { value: ListTransactionsOrdering; label: string }[] = [
  { value: "-date", label: "Newest first" },
  { value: "date", label: "Oldest first" },
  { value: "-amount", label: "Amount high→low" },
  { value: "amount", label: "Amount low→high" },
  { value: "merchant", label: "Merchant A–Z" },
  { value: "-merchant", label: "Merchant Z–A" },
]

/** Card mode has no column headers to click: this select sorts instead. */
export function TransactionsSortSelect({
  ordering,
  onChange,
}: {
  ordering: ListTransactionsOrdering | null
  onChange: (ordering: ListTransactionsOrdering) => void
}) {
  return (
    <FilterSelect
      aria-label="Sort"
      className="w-auto"
      value={ordering ?? "-date"}
      onChange={(e) => onChange(e.target.value as ListTransactionsOrdering)}
    >
      {SORT_OPTIONS.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </FilterSelect>
  )
}
