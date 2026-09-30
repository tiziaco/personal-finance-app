"use client"

import { useId } from "react"
import { Input } from "@app/ui/input"
import {
  EMPTY_DATE_FILTER,
  usesFrom,
  usesTo,
  type DateFilterMode,
  type DateFilterValue,
} from "../url-state/date-filter"
import { labels } from "../labels"
import { FilterField, FilterSelect } from "./filter-panel"

/**
 * Mode first, then the inputs that mode uses. The mode is its own URL key, so
 * "mode picked, no date yet" survives a reload and the inputs stay visible.
 */
export function DateFilterControl({
  label,
  value,
  onChange,
}: {
  label: string
  value: DateFilterValue
  onChange: (value: DateFilterValue) => void
}) {
  const id = useId()
  return (
    <FilterField label={label} htmlFor={`${id}-mode`}>
      <FilterSelect
        id={`${id}-mode`}
        value={value.mode ?? ""}
        onChange={(e) => {
          const mode = (e.target.value || null) as DateFilterMode | null
          onChange(mode ? { ...value, mode } : EMPTY_DATE_FILTER)
        }}
      >
        <option value="">{labels.anyDate}</option>
        <option value="gte">{labels.onOrAfter}</option>
        <option value="lte">{labels.onOrBefore}</option>
        <option value="range">{labels.between}</option>
      </FilterSelect>
      {usesFrom(value.mode) && (
        <Input
          type="date"
          aria-label={labels.dateFrom(label)}
          value={value.date1}
          onChange={(e) => onChange({ ...value, date1: e.target.value })}
        />
      )}
      {usesTo(value.mode) && (
        <Input
          type="date"
          aria-label={labels.dateTo(label)}
          value={value.date2}
          onChange={(e) => onChange({ ...value, date2: e.target.value })}
        />
      )}
    </FilterField>
  )
}
