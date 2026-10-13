"use client"

import type { Dispatch, SetStateAction } from "react"
import {
  FilterField,
  FilterPanel,
  FilterSelect,
} from "@app/data-table/filters/filter-panel"
import { FilterChip } from "@app/data-table/filters/filter-chip"
import { FilterCheckboxGroup } from "@app/data-table/filters/filter-checkbox-group"
import { DateFilterControl } from "@app/data-table/filters/date-filter-control"
import {
  EMPTY_DATE_FILTER,
  dateFilterLabel,
  isDateFilterActive,
} from "@app/data-table/url-state/date-filter"
import type { CategoryResponse } from "@app/api-client/types"
import { Input } from "@app/ui/input"
import {
  EMPTY_TRANSACTIONS_FILTERS,
  type TransactionsFilters,
} from "./transactions-table-params"

type SetFilters = Dispatch<SetStateAction<TransactionsFilters>>

// Every filter in the panel has a chip below, and both count it as active the same way.
const activeCount = (f: TransactionsFilters) =>
  [
    f.categories.length > 0,
    f.amountMin != null,
    f.amountMax != null,
    f.recurring != null,
    isDateFilterActive(f.date),
  ].filter(Boolean).length

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
      activeCount={activeCount(filters)}
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
      <FilterField label="Min amount" htmlFor="transactions-amount-min">
        <Input
          id="transactions-amount-min"
          type="number"
          step="0.01"
          inputMode="decimal"
          value={filters.amountMin ?? ""}
          onChange={(e) =>
            setFilters((f) => ({ ...f, amountMin: e.target.value || null }))
          }
        />
      </FilterField>
      <FilterField label="Max amount" htmlFor="transactions-amount-max">
        <Input
          id="transactions-amount-max"
          type="number"
          step="0.01"
          inputMode="decimal"
          value={filters.amountMax ?? ""}
          onChange={(e) =>
            setFilters((f) => ({ ...f, amountMax: e.target.value || null }))
          }
        />
      </FilterField>
      <FilterField label="Recurring" htmlFor="transactions-recurring">
        <FilterSelect
          id="transactions-recurring"
          value={filters.recurring == null ? "" : String(filters.recurring)}
          onChange={(e) => {
            const v = e.target.value
            setFilters((f) => ({
              ...f,
              recurring: v === "" ? null : v === "true",
            }))
          }}
        >
          <option value="">Any</option>
          <option value="true">Recurring</option>
          <option value="false">Not recurring</option>
        </FilterSelect>
      </FilterField>
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
