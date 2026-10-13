"use client"

import { useId } from "react"
import { Checkbox } from "@app/ui/checkbox"

/** Several values from a fixed list. The value keeps the options' order. */
export function FilterCheckboxGroup<T extends string>({
  label,
  options,
  value,
  onChange,
}: {
  label: string
  options: { value: T; label: string }[]
  value: T[]
  onChange: (value: T[]) => void
}) {
  const id = useId()
  const chosen = new Set(value)
  const toggle = (option: T, on: boolean) => {
    const next = new Set(chosen)
    if (on) next.add(option)
    else next.delete(option)
    onChange(options.map((o) => o.value).filter((v) => next.has(v)))
  }
  return (
    <fieldset className="space-y-1">
      <legend className="text-xs font-medium text-muted-foreground">
        {label}
      </legend>
      <div className="max-h-48 space-y-1 overflow-y-auto pr-1">
        {options.map((o) => (
          <label
            key={o.value}
            htmlFor={`${id}-${o.value}`}
            className="flex items-center gap-2 text-sm"
          >
            <Checkbox
              id={`${id}-${o.value}`}
              checked={chosen.has(o.value)}
              onCheckedChange={(on) => toggle(o.value, on)}
            />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  )
}
