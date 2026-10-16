import type {
  MonthOfYearResponse,
  WeekdaySpendResponse,
} from "@app/api-client/types"
import { formatAmount } from "@/components/transactions/format"
import { formatIndex } from "./format"

/** One weekday as the chart draws it; the `*Text` fields are ready to show. */
export type WeekdayPoint = {
  /** Short weekday, "Mon", for the axis. */
  label: string
  /** Long weekday, "Monday", for the tooltip and table. */
  name: string
  perDay: number
  perDayText: string
  count: number
  averageText: string
  days: number
}

/** One calendar month; `average` is null with no history, so the chart draws no bar. */
export type MonthOfYearPoint = {
  label: string
  average: number | null
  averageText: string
  indexText: string
  years: number
}

const SHORT_WEEKDAY = new Intl.DateTimeFormat(undefined, { weekday: "short" })
const LONG_WEEKDAY = new Intl.DateTimeFormat(undefined, { weekday: "long" })

/** Keeps the server's order (Monday first); names are in the browser's language. */
export function toWeekdayPoints(days: WeekdaySpendResponse[]): WeekdayPoint[] {
  return days.map((d) => ({
    // 1 Jan 2024 was a Monday, and weekday 0 is Monday.
    label: SHORT_WEEKDAY.format(new Date(2024, 0, 1 + d.weekday)),
    name: LONG_WEEKDAY.format(new Date(2024, 0, 1 + d.weekday)),
    perDay: Number(d.per_day),
    perDayText: formatAmount(d.per_day),
    count: d.count,
    averageText: formatAmount(d.average),
    days: d.days,
  }))
}

const SHORT_MONTH = new Intl.DateTimeFormat(undefined, { month: "short" })

export function toMonthOfYearPoints(
  months: MonthOfYearResponse[],
): MonthOfYearPoint[] {
  return months.map((m) => ({
    label: SHORT_MONTH.format(new Date(2000, m.month - 1, 1)),
    average: m.years === 0 ? null : Number(m.average_spend),
    averageText: formatAmount(m.average_spend),
    indexText: formatIndex(m.index),
    years: m.years,
  }))
}
