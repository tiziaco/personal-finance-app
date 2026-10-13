import type { DateFilterValue } from "./date-filter"

export const DATE_PRESETS = [
  "today",
  "this_week",
  "this_month",
  "last_month",
] as const
export type DatePreset = (typeof DATE_PRESETS)[number]

const pad = (n: number) => String(n).padStart(2, "0")
/** Local calendar date as ISO YYYY-MM-DD — never toISOString, which is UTC. */
const iso = (d: Date) =>
  `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
const range = (from: Date, to: Date): DateFilterValue => ({
  mode: "range",
  date1: iso(from),
  date2: iso(to),
})

/** A preset as a closed range around `today`. Weeks start on Monday. */
export function datePresetValue(
  preset: DatePreset,
  today: Date,
): DateFilterValue {
  const y = today.getFullYear()
  const m = today.getMonth()
  const d = today.getDate()
  switch (preset) {
    case "today":
      return range(today, today)
    case "this_week": {
      const back = (today.getDay() + 6) % 7 // days since Monday
      return range(new Date(y, m, d - back), new Date(y, m, d - back + 6))
    }
    case "this_month":
      return range(new Date(y, m, 1), new Date(y, m + 1, 0))
    case "last_month":
      return range(new Date(y, m - 1, 1), new Date(y, m, 0))
  }
}
