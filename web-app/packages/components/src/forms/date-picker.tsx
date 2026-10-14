"use client"

import { useState } from "react"
import { CalendarIcon } from "lucide-react"
import { Button } from "@app/ui/button"
import { Calendar } from "@app/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@app/ui/popover"
import { cn } from "@app/core/lib/utils"

const pad = (n: number) => String(n).padStart(2, "0")
/** Local calendar date ↔ ISO YYYY-MM-DD. Never toISOString, which is UTC and shifts the day. */
const toIso = (d: Date) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const fromIso = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number)
  return new Date(y, m - 1, d)
}
const display = new Intl.DateTimeFormat(undefined, {
  day: "numeric",
  month: "short",
  year: "numeric",
})

/**
 * One day, picked from a calendar in a popover. The value is a local ISO date, "" when empty.
 * Without a `<label>`, `aria-label` names it; the name still ends with the day shown.
 */
export function DatePicker({
  value,
  onChange,
  id,
  placeholder = "Pick a date",
  "aria-label": ariaLabel,
}: {
  value: string
  onChange: (iso: string) => void
  id?: string
  placeholder?: string
  "aria-label"?: string
}) {
  const [open, setOpen] = useState(false)
  const selected = value ? fromIso(value) : undefined
  const shown = selected ? display.format(selected) : placeholder
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger
        render={
          <Button
            id={id}
            aria-label={ariaLabel && `${ariaLabel}, ${shown}`}
            variant="outline"
            className={cn(
              "w-full justify-start font-normal",
              !selected && "text-muted-foreground",
            )}
          />
        }
      >
        <CalendarIcon />
        {shown}
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={selected}
          defaultMonth={selected}
          onSelect={(day) => {
            if (day) onChange(toIso(day))
            setOpen(false)
          }}
        />
      </PopoverContent>
    </Popover>
  )
}
