// apps/web/src/components/orders/orders-filters.tsx
"use client"

import type { Dispatch, SetStateAction } from "react"
import {
  FilterField,
  FilterPanel,
  FilterSelect,
} from "@app/data-table/filters/filter-panel"
import { FilterChip } from "@app/data-table/filters/filter-chip"
import { DateFilterControl } from "@app/data-table/filters/date-filter-control"
import {
  EMPTY_DATE_FILTER,
  dateFilterLabel,
  isDateFilterActive,
} from "@app/data-table/url-state/date-filter"
import type { CustomerResponse } from "@app/api-client/types"
import {
  EMPTY_ORDERS_FILTERS,
  ORDER_STATUSES,
  ORDER_STATUS_LABELS,
  type OrderStatus,
  type OrdersFilters,
} from "./orders-table-params"

type Props = {
  customers: CustomerResponse[]
  filters: OrdersFilters
  setFilters: Dispatch<SetStateAction<OrdersFilters>>
}

// Every filter in the panel has a chip below, and both count it as active the same way.
const activeCount = (f: OrdersFilters) =>
  [f.status !== null, f.customer !== null, isDateFilterActive(f.created)].filter(Boolean)
    .length

export function OrdersFilterPanel({ customers, filters, setFilters }: Props) {
  return (
    <FilterPanel
      activeCount={activeCount(filters)}
      onClearAll={() => setFilters(EMPTY_ORDERS_FILTERS)}
    >
      <FilterField label="Status" htmlFor="orders-status">
        <FilterSelect
          id="orders-status"
          value={filters.status ?? ""}
          onChange={(e) => {
            const status = (e.target.value || null) as OrderStatus | null
            setFilters((f) => ({ ...f, status }))
          }}
        >
          <option value="">Any status</option>
          {ORDER_STATUSES.map((s) => (
            <option key={s} value={s}>
              {ORDER_STATUS_LABELS[s]}
            </option>
          ))}
        </FilterSelect>
      </FilterField>
      <FilterField label="Customer" htmlFor="orders-customer">
        <FilterSelect
          id="orders-customer"
          value={filters.customer ?? ""}
          onChange={(e) => {
            const customer = e.target.value === "" ? null : Number(e.target.value)
            setFilters((f) => ({ ...f, customer }))
          }}
        >
          <option value="">Any customer</option>
          {customers.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </FilterSelect>
      </FilterField>
      <DateFilterControl
        label="Created"
        value={filters.created}
        onChange={(created) => setFilters((f) => ({ ...f, created }))}
      />
    </FilterPanel>
  )
}

export function OrdersFilterChips({ customers, filters, setFilters }: Props) {
  const createdLabel = dateFilterLabel("Created", filters.created)
  const customerName =
    customers.find((c) => c.id === filters.customer)?.name ?? `#${filters.customer}`
  return (
    <>
      {filters.status && (
        <FilterChip
          label={`Status: ${ORDER_STATUS_LABELS[filters.status]}`}
          onRemove={() => setFilters((f) => ({ ...f, status: null }))}
        />
      )}
      {filters.customer !== null && (
        <FilterChip
          label={`Customer: ${customerName}`}
          onRemove={() => setFilters((f) => ({ ...f, customer: null }))}
        />
      )}
      {createdLabel && (
        <FilterChip
          label={createdLabel}
          onRemove={() => setFilters((f) => ({ ...f, created: EMPTY_DATE_FILTER }))}
        />
      )}
    </>
  )
}
