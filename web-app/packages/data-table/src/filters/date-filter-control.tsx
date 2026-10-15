"use client"

import { useId } from "react"
import { Button } from "@app/ui/button"
import { cn } from "@app/core/lib/utils"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@app/ui/select"
import { DatePicker } from "@app/components/forms/date-picker"
import {
  EMPTY_DATE_FILTER,
  usesFrom,
  usesTo,
  type DateFilterMode,
  type DateFilterValue,
} from "../url-state/date-filter"
import { DATE_PRESETS, datePresetValue } from "../url-state/date-presets"
import { labels } from "../labels"
import { FilterField } from "./filter-panel"

// null is "Any date": Base UI's Select models no value as null.
const MODES: { value: DateFilterMode | null; label: string }[] = [
  { value: null, label: labels.anyDate },
  { value: "gte", label: labels.onOrAfter },
  { value: "lte", label: labels.onOrBefore },
  { value: "range", label: labels.between },
]

/**
 * Mode first, then the inputs that mode uses. The mode is its own URL key, so
 * "mode picked, no date yet" survives a reload and the inputs stay visible.
 */
export function DateFilterControl({
  label,
  value,
  onChange,
  presets = false,
}: {
  label: string
  value: DateFilterValue
  onChange: (value: DateFilterValue) => void
  /** quick ranges (today, this week, …) above the mode select */
  presets?: boolean
}) {
  const id = useId()
  return (
    <FilterField label={label} htmlFor={`${id}-mode`}>
      {presets && (
        <div className="flex flex-wrap gap-1">
          {DATE_PRESETS.map((preset) => (
            <Button
              key={preset}
              type="button"
              variant="outline"
              size="xs"
              onClick={() => onChange(datePresetValue(preset, new Date()))}
            >
              {labels.datePresets[preset]}
            </Button>
          ))}
        </div>
      )}
      <Select
        items={MODES}
        value={value.mode}
        onValueChange={(mode) =>
          onChange(mode ? { ...value, mode } : EMPTY_DATE_FILTER)
        }
      >
        <SelectTrigger id={`${id}-mode`} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {MODES.map((m) => (
            <SelectItem key={m.value ?? "any"} value={m.value}>
              {m.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {(usesFrom(value.mode) || usesTo(value.mode)) && (
        <div
          className={cn("grid gap-2", value.mode === "range" && "grid-cols-2")}
        >
          {usesFrom(value.mode) && (
            <DatePicker
              aria-label={labels.dateFrom(label)}
              value={value.date1}
              onChange={(date1) => onChange({ ...value, date1 })}
            />
          )}
          {usesTo(value.mode) && (
            <DatePicker
              aria-label={labels.dateTo(label)}
              value={value.date2}
              onChange={(date2) => onChange({ ...value, date2 })}
            />
          )}
        </div>
      )}
    </FilterField>
  )
}
