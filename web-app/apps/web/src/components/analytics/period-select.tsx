import { cn } from "@app/core/lib/utils"
import { Button } from "@app/ui/button"

import { formatPeriod } from "./format"

/** A row of period choices (in months); the chosen one is pressed. */
export function PeriodSelect({
  choices,
  value,
  onChange,
}: {
  choices: readonly number[]
  value: number
  onChange: (months: number) => void
}) {
  return (
    <div role="group" aria-label="Period" className="flex flex-wrap gap-1">
      {choices.map((months) => (
        <Button
          key={months}
          type="button"
          size="sm"
          variant={months === value ? "default" : "outline"}
          aria-pressed={months === value}
          onClick={() => onChange(months)}
        >
          {months === 1 ? "1 month" : `${months} months`}
        </Button>
      ))}
    </div>
  )
}

/**
 * A tab's header: the period choices, then the period the figures cover once
 * one has loaded, dimmed while those figures are the previous period's.
 */
export function PeriodHeader({
  choices,
  value,
  onChange,
  range,
  dimmed,
}: {
  choices: readonly number[]
  value: number
  onChange: (months: number) => void
  range: { date_from: string | null; date_to: string | null } | undefined
  dimmed: boolean
}) {
  const period = range && formatPeriod(range.date_from, range.date_to)
  return (
    <header className="flex flex-col gap-3">
      <PeriodSelect choices={choices} value={value} onChange={onChange} />
      {period ? (
        <p
          className={cn(
            "text-sm text-muted-foreground",
            dimmed && "opacity-60",
          )}
        >
          {period}
        </p>
      ) : null}
    </header>
  )
}
