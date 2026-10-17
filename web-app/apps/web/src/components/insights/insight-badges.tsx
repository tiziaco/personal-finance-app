import type { InsightResponse } from "@app/api-client/types"
import { Badge } from "@app/ui/badge"
import { formatKeyFigure } from "./key-figure"
import { monthSoFar, SECTION_LABEL } from "./labels"
import { SEVERITY_LABEL } from "./severity"

/** A card's chip row: severity, optional section, "<Month> so far", optional key figure. */
export function InsightBadges({
  insight,
  showSection,
  showKeyFigure,
  monthToDateThrough,
}: {
  insight: InsightResponse
  showSection: boolean
  showKeyFigure: boolean
  monthToDateThrough: string | null | undefined
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Badge variant="outline">{SEVERITY_LABEL[insight.severity]}</Badge>
      {showSection && (
        <Badge variant="secondary">{SECTION_LABEL[insight.section]}</Badge>
      )}
      {insight.period === "month_to_date" && (
        <Badge variant="secondary">{monthSoFar(monthToDateThrough)}</Badge>
      )}
      {showKeyFigure && insight.key_figure && (
        <Badge>{formatKeyFigure(insight.key_figure)}</Badge>
      )}
    </div>
  )
}
