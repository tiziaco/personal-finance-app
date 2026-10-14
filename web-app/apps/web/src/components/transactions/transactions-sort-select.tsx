"use client"

import { ArrowDown, ArrowUp } from "lucide-react"
import type { ListTransactionsOrdering } from "@app/api-client/types"
import { FilterSelect } from "@app/data-table/filters/filter-panel"
import { Button } from "@app/ui/button"

const FIELDS = [
  { value: "date", label: "Date" },
  { value: "amount", label: "Amount" },
  { value: "merchant", label: "Merchant" },
] as const
type SortField = (typeof FIELDS)[number]["value"]

const toOrdering = (field: SortField, desc: boolean) =>
  `${desc ? "-" : ""}${field}` as ListTransactionsOrdering

/**
 * Legacy's sort: a field and a direction, on every screen size. It reads and
 * writes the same `ordering` as a header click, so the two always agree. No
 * ordering is the list's default, newest first.
 */
export function TransactionsSortControl({
  ordering,
  onChange,
}: {
  ordering: ListTransactionsOrdering | null
  onChange: (ordering: ListTransactionsOrdering) => void
}) {
  const current = ordering ?? "-date"
  const desc = current.startsWith("-")
  const field = current.replace(/^-/, "") as SortField
  return (
    <div className="flex items-center gap-1">
      <FilterSelect
        aria-label="Sort by"
        className="w-auto"
        value={field}
        onChange={(e) =>
          onChange(toOrdering(e.target.value as SortField, desc))
        }
      >
        {FIELDS.map((f) => (
          <option key={f.value} value={f.value}>
            {f.label}
          </option>
        ))}
      </FilterSelect>
      <Button
        variant="outline"
        size="icon-sm"
        aria-label={desc ? "Switch to ascending" : "Switch to descending"}
        onClick={() => onChange(toOrdering(field, !desc))}
      >
        {desc ? <ArrowDown /> : <ArrowUp />}
      </Button>
    </div>
  )
}
