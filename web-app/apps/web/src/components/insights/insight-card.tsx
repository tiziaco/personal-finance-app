import Link from "next/link"
import type { InsightResponse } from "@app/api-client/types"
import { Card, CardContent } from "@app/ui/card"
import { InsightBadges } from "./insight-badges"
import { insightHref } from "./insight-link"

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
        <InsightBadges
          insight={insight}
          showSection={showSection}
          showKeyFigure
          monthToDateThrough={monthToDateThrough}
        />
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
