import type { InsightResponse } from "@app/api-client/types"

type Severity = InsightResponse["severity"]

/** Most pressing first. */
export const SEVERITY_ORDER: Severity[] = [
  "critical",
  "high",
  "medium",
  "low",
  "info",
]

export const SEVERITY_LABEL: Record<Severity, string> = {
  critical: "Critical",
  high: "High",
  medium: "Medium",
  low: "Low",
  info: "Info",
}

/** A new array, most severe first; equal severities keep the server's order. */
export function sortBySeverity(insights: InsightResponse[]): InsightResponse[] {
  const rank = (i: InsightResponse) => SEVERITY_ORDER.indexOf(i.severity)
  return insights
    .map((insight, index) => ({ insight, index }))
    .sort((a, b) => rank(a.insight) - rank(b.insight) || a.index - b.index)
    .map(({ insight }) => insight)
}
