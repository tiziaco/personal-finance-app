"use client"

import {
  useCallback,
  useEffect,
  useState,
  type Dispatch,
  type SetStateAction,
} from "react"
import {
  FilterPanel,
  FilterSection,
} from "@app/data-table/filters/filter-panel"
import { FilterChip } from "@app/data-table/filters/filter-chip"
import { FilterCheckboxGroup } from "@app/data-table/filters/filter-checkbox-group"
import { DateFilterControl } from "@app/data-table/filters/date-filter-control"
import { SEARCH_DEBOUNCE_MS } from "@app/data-table/url-state/use-url-table-state"
import {
  EMPTY_DATE_FILTER,
  dateFilterLabel,
} from "@app/data-table/url-state/date-filter"
import type { CategoryResponse } from "@app/api-client/types"
import { Input } from "@app/ui/input"
import { Label } from "@app/ui/label"
import { Switch } from "@app/ui/switch"
import { parseAmount } from "./amount-input"
import {
  EMPTY_TRANSACTIONS_FILTERS,
  activeFilterCount,
  type TransactionsFilters,
} from "./transactions-table-params"

type SetFilters = Dispatch<SetStateAction<TransactionsFilters>>

/**
 * One amount bound. The typed text is a draft: it reaches the URL (one
 * history entry, one request) only once it is an amount and the user pauses,
 * or leaves the field. Clearing it applies at once.
 */
function AmountBound({
  id,
  label,
  value,
  onCommit,
}: {
  id: string
  label: string
  value: string | null
  onCommit: (value: string | null) => void
}) {
  const [draft, setDraft] = useState(value ?? "")
  // The value last seen from the URL: a change there (a chip removed, "Clear
  // all", Back) replaces the draft; this field's own commit does not.
  const [seen, setSeen] = useState(value)
  if (value !== seen) {
    setSeen(value)
    setDraft(value ?? "")
  }
  const parsed = draft.trim() === "" ? null : parseAmount(draft)
  const invalid = draft.trim() !== "" && parsed === null

  const commit = useCallback(() => {
    if (invalid || parsed === value) return
    setSeen(parsed)
    onCommit(parsed)
  }, [invalid, parsed, value, onCommit])

  useEffect(() => {
    if (invalid || parsed === value) return
    // The same pause as search.
    const timer = setTimeout(commit, parsed === null ? 0 : SEARCH_DEBOUNCE_MS)
    return () => clearTimeout(timer)
  }, [commit, invalid, parsed, value])

  return (
    <div className="space-y-1">
      <Label htmlFor={id} className="text-xs font-normal text-muted-foreground">
        {label}
      </Label>
      <Input
        id={id}
        inputMode="decimal"
        placeholder="-50.00"
        aria-invalid={invalid || undefined}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={commit}
      />
    </div>
  )
}

export function TransactionsFilterPanel({
  filters,
  setFilters,
  categories,
}: {
  filters: TransactionsFilters
  setFilters: SetFilters
  categories: CategoryResponse[]
}) {
  return (
    <FilterPanel
      activeCount={activeFilterCount(filters)}
      onClearAll={() => setFilters(EMPTY_TRANSACTIONS_FILTERS)}
    >
      <DateFilterControl
        label="Date"
        presets
        value={filters.date}
        onChange={(date) => setFilters((f) => ({ ...f, date }))}
      />
      <FilterCheckboxGroup
        label="Category"
        options={categories.map((c) => ({ value: c.value, label: c.label }))}
        value={filters.categories}
        onChange={(next) => setFilters((f) => ({ ...f, categories: next }))}
      />
      <FilterSection title="Amount range">
        <div className="grid grid-cols-2 gap-2">
          <AmountBound
            id="transactions-amount-min"
            label="Min"
            value={filters.amountMin}
            onCommit={(amountMin) => setFilters((f) => ({ ...f, amountMin }))}
          />
          <AmountBound
            id="transactions-amount-max"
            label="Max"
            value={filters.amountMax}
            onCommit={(amountMax) => setFilters((f) => ({ ...f, amountMax }))}
          />
        </div>
      </FilterSection>
      <div className="flex items-center justify-between gap-4">
        <div>
          <Label htmlFor="transactions-recurring">Recurring only</Label>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Show only recurring transactions
          </p>
        </div>
        <Switch
          id="transactions-recurring"
          checked={filters.recurring === true}
          onCheckedChange={(on) =>
            setFilters((f) => ({ ...f, recurring: on ? true : null }))
          }
        />
      </div>
    </FilterPanel>
  )
}

export function TransactionsFilterChips({
  filters,
  setFilters,
  label,
}: {
  filters: TransactionsFilters
  setFilters: SetFilters
  label: (slug: string) => string
}) {
  const dateLabel = dateFilterLabel("Date", filters.date)
  return (
    <>
      {filters.categories.map((c) => (
        <FilterChip
          key={c}
          label={`Category: ${label(c)}`}
          onRemove={() =>
            setFilters((f) => ({
              ...f,
              categories: f.categories.filter((x) => x !== c),
            }))
          }
        />
      ))}
      {filters.amountMin != null && (
        <FilterChip
          label={`Amount ≥ ${filters.amountMin}`}
          onRemove={() => setFilters((f) => ({ ...f, amountMin: null }))}
        />
      )}
      {filters.amountMax != null && (
        <FilterChip
          label={`Amount ≤ ${filters.amountMax}`}
          onRemove={() => setFilters((f) => ({ ...f, amountMax: null }))}
        />
      )}
      {filters.recurring != null && (
        <FilterChip
          label={filters.recurring ? "Recurring" : "Not recurring"}
          onRemove={() => setFilters((f) => ({ ...f, recurring: null }))}
        />
      )}
      {dateLabel && (
        <FilterChip
          label={dateLabel}
          onRemove={() =>
            setFilters((f) => ({ ...f, date: EMPTY_DATE_FILTER }))
          }
        />
      )}
    </>
  )
}
