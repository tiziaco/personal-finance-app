import { Button } from "@app/ui/button"

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
