"use client"

import { ArrowDown, ArrowUp } from "lucide-react"
import type { ListTransactionsOrdering } from "@app/api-client/types"
import { Button } from "@app/ui/button"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@app/ui/select"

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
      <Select
        items={FIELDS}
        value={field}
        onValueChange={(next) => next && onChange(toOrdering(next, desc))}
      >
        <SelectTrigger size="sm" aria-label="Sort by" className="w-32">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {FIELDS.map((f) => (
            <SelectItem key={f.value} value={f.value}>
              {f.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
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
