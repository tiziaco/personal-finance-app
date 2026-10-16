import { formatMonth } from "@/components/dashboard/month"

export type Tone = "good" | "bad" | "neutral"

const MONTHS = { month: "short", year: "numeric" } as const
const DAYS = { day: "numeric", month: "short", year: "numeric" } as const
const DAY_MONTH = { day: "numeric", month: "short" } as const

/** "YYYY-MM-DD" → a local-time Date (no UTC shift). */
function parseDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number)
  return new Date(y, m - 1, d)
}

function range(options: Intl.DateTimeFormatOptions, from: Date, to: Date) {
  return new Intl.DateTimeFormat(undefined, options).formatRange(from, to)
}

/** The period an analytics figure covers: whole months by month, anything else by day. */
export function formatPeriod(
  dateFrom: string | null,
  dateTo: string | null,
): string | null {
  if (!dateFrom || !dateTo) return null
  const from = parseDate(dateFrom)
  const to = parseDate(dateTo)
  const wholeMonths =
    from.getDate() === 1 &&
    to.getDate() === new Date(to.getFullYear(), to.getMonth() + 1, 0).getDate()
  if (!wholeMonths) return range(DAYS, from, to)
  if (dateFrom.slice(0, 7) === dateTo.slice(0, 7))
    return formatMonth(dateFrom.slice(0, 7))
  return range(MONTHS, from, to)
}

/** One decimal, the locale's digits, the sign kept: 8.24 → "8.2%". */
export function formatPct(pct: number): string {
  const number = new Intl.NumberFormat(undefined, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(pct)
  return `${number}%`
}

/** Whether a change is good news: spending down and income up are good. */
export function changeTone(pct: number | null, kind: "spend" | "income"): Tone {
  if (pct === null || pct === 0) return "neutral"
  const up = pct > 0
  return up === (kind === "income") ? "good" : "bad"
}

/** The seasonal index (100 = typical) as words. */
export function formatIndex(index: number | null): string {
  if (index === null) return "no data yet"
  const diff = Math.round(index - 100)
  if (diff === 0) return "a typical month"
  return `${Math.abs(diff)}% ${diff > 0 ? "above" : "below"} a typical month`
}

/** Days 1 to `day` of a "YYYY-MM" month, clamped to the month's length. */
export function formatDayRange(month: string, day: number): string {
  const [y, m] = month.split("-").map(Number)
  const last = new Date(y, m, 0).getDate()
  return range(
    DAY_MONTH,
    new Date(y, m - 1, 1),
    new Date(y, m - 1, Math.min(day, last)),
  )
}

/** "1 purchase", "2 purchases". */
export function purchases(n: number): string {
  return `${n} ${n === 1 ? "purchase" : "purchases"}`
}

export type PartialLabel = "so far" | "partial"

/**
 * How to name a partial month: "so far" only for the month in progress (the
 * server's month-to-date month, compared as text, no clock); any other partial
 * month, such as a first month of data starting late, is just "partial".
 */
export function partialLabel(
  partial: boolean,
  month: string,
  currentMonth: string | null | undefined,
): PartialLabel | null {
  if (!partial) return null
  return month === currentMonth ? "so far" : "partial"
}
