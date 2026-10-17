import type {
  InsightLinkResponse,
  InsightResponse,
} from "@app/api-client/types"
import { parseIsoDay, toIsoDay } from "@app/core/lib/dates"

/** The first and last day of a "YYYY-MM" month. */
function monthSpan(month: string): [string, string] | null {
  const first = parseIsoDay(`${month}-01`)
  if (!first) return null
  const last = new Date(first.getFullYear(), first.getMonth() + 1, 0)
  return [toIsoDay(first), toIsoDay(last)]
}

/** The day range a card describes, or null when the response lacks the month. */
function periodSpan(
  period: InsightResponse["period"],
  referenceMonth: string | null | undefined,
  monthToDateThrough: string | null | undefined,
): [string, string] | null {
  if (period === "month") {
    return referenceMonth ? monthSpan(referenceMonth) : null
  }
  if (!monthToDateThrough || !parseIsoDay(monthToDateThrough)) return null
  const span = monthSpan(monthToDateThrough.slice(0, 7))
  return span ? [span[0], monthToDateThrough] : null
}

/** Where a card's link leads: the transactions page, filtered to what the card is about. */
export function insightHref(
  link: InsightLinkResponse | null | undefined,
  period: InsightResponse["period"],
  referenceMonth: string | null | undefined,
  monthToDateThrough: string | null | undefined,
): string | null {
  if (!link) return null
  if (link.kind === "recurring") return "/transactions?is_recurring=true"

  const span = periodSpan(period, referenceMonth, monthToDateThrough)
  if (!span) return null
  const dates = `date_from=${span[0]}&date_to=${span[1]}`

  if (link.kind === "category") {
    return link.category
      ? `/transactions?category=${encodeURIComponent(link.category)}&${dates}`
      : null
  }
  return link.merchant
    ? `/transactions?search=${encodeURIComponent(link.merchant)}&${dates}`
    : null
}
