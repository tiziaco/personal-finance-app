import type { InsightResponse } from "@app/api-client/types"
import { parseIsoDay } from "@app/core/lib/dates"

export const SECTION_LABEL: Record<InsightResponse["section"], string> = {
  spending: "Spending",
  recurring: "Recurring",
  savings: "Savings",
  anomalies: "Anomalies",
  comparisons: "Comparisons",
}

/** Section tab order. */
export const SECTIONS: readonly InsightResponse["section"][] = [
  "spending",
  "recurring",
  "savings",
  "anomalies",
  "comparisons",
]

export const NOTHING_STANDS_OUT = "Nothing stands out this month."

/** "2026-10-14" → "October so far". */
export function monthSoFar(through: string | null | undefined) {
  const day = through ? parseIsoDay(through) : undefined
  if (!day) return "Month so far"
  const month = new Intl.DateTimeFormat(undefined, { month: "long" }).format(
    day,
  )
  return `${month} so far`
}

const generatedFormat = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
})

/** "Generated Oct 14, 2026, 9:30 AM", or null when the time is missing or invalid. */
export function generatedLabel(generatedAt: string | null | undefined) {
  const date = generatedAt ? new Date(generatedAt) : null
  return date && !Number.isNaN(date.getTime())
    ? `Generated ${generatedFormat.format(date)}`
    : null
}
