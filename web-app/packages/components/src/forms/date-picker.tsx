"use client"

import { useState } from "react"
import { CalendarIcon } from "lucide-react"
import { Button } from "@app/ui/button"
import { Calendar } from "@app/ui/calendar"
import { Popover, PopoverContent, PopoverTrigger } from "@app/ui/popover"
import { cn } from "@app/core/lib/utils"
import { formatDay, parseIsoDay, toIsoDay } from "@app/core/lib/dates"

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
  // A malformed value (a hand-edited URL) shows as empty rather than throwing.
  const selected = parseIsoDay(value)
  const shown = selected ? formatDay(selected) : placeholder
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
          // Monday first, like the date filter's "this week" preset.
          weekStartsOn={1}
          selected={selected}
          defaultMonth={selected}
          onSelect={(day) => {
            if (day) onChange(toIsoDay(day))
            setOpen(false)
          }}
        />
      </PopoverContent>
    </Popover>
  )
}
