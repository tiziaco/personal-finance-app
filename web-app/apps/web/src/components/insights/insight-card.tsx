import Link from "next/link"
import type { InsightResponse } from "@app/api-client/types"
import { parseIsoDay } from "@app/core/lib/dates"
import { Badge } from "@app/ui/badge"
import { Card, CardContent } from "@app/ui/card"
import { insightHref } from "./insight-link"
import { formatKeyFigure } from "./key-figure"
import { SEVERITY_LABEL } from "./severity"

export const SECTION_LABEL: Record<InsightResponse["section"], string> = {
  spending: "Spending",
  recurring: "Recurring",
  savings: "Savings",
  anomalies: "Anomalies",
  comparisons: "Comparisons",
}

/** "2026-10-14" → "October so far". */
export function monthSoFar(through: string | null | undefined) {
  const day = through ? parseIsoDay(through) : undefined
  if (!day) return "Month so far"
  const month = new Intl.DateTimeFormat(undefined, { month: "long" }).format(
    day,
  )
  return `${month} so far`
}

export function InsightCard({
  insight,
  showSection,
  referenceMonth,
  monthToDateThrough,
}: {
  insight: InsightResponse
  /** The All tab tags each card with its section. */
  showSection: boolean
  referenceMonth: string | null | undefined
  monthToDateThrough: string | null | undefined
}) {
  const href = insightHref(
    insight.link,
    insight.period,
    referenceMonth,
    monthToDateThrough,
  )
  return (
    <Card>
      <CardContent className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="outline">{SEVERITY_LABEL[insight.severity]}</Badge>
          {showSection && (
            <Badge variant="secondary">{SECTION_LABEL[insight.section]}</Badge>
          )}
          {insight.period === "month_to_date" && (
            <Badge variant="secondary">{monthSoFar(monthToDateThrough)}</Badge>
          )}
          {insight.key_figure && (
            <Badge>{formatKeyFigure(insight.key_figure)}</Badge>
          )}
        </div>
        <p data-testid="insight-summary" className="text-sm font-medium">
          {insight.summary}
        </p>
        <p className="text-sm text-muted-foreground">{insight.narrative}</p>
        {href && (
          <Link
            href={href}
            className="inline-block text-sm underline underline-offset-4"
          >
            View transactions
          </Link>
        )}
      </CardContent>
    </Card>
  )
}
