"use client"

import Link from "next/link"
import { useGetInsights } from "@app/api-client/endpoints/insights"
import { Card, CardContent } from "@app/ui/card"
import { Skeleton } from "@app/ui/skeleton"
import { InsightBadges } from "@/components/insights/insight-badges"
import {
  generatedLabel,
  NOTHING_STANDS_OUT,
} from "@/components/insights/labels"
import { sortBySeverity } from "@/components/insights/severity"
import { SectionError } from "./section-error"

const LINK = "text-sm underline underline-offset-4"
const TOP = 3

const STALE_NOTE = {
  new_month: "A new month has started since these were written.",
  data_changed:
    "You've added or changed transactions since these were written.",
} as const

/**
 * The home page's read-only view of the stored insights. It never generates:
 * a stale or missing set sends the user to /insights, which does.
 */
export function InsightsCallout() {
  const query = useGetInsights({ query: { meta: { silentError: true } } })
  const data = query.data

  if (!data) {
    return query.isError ? (
      <SectionError what="your insights" onRetry={() => void query.refetch()} />
    ) : (
      <Skeleton data-testid="callout-skeleton" className="h-40 w-full" />
    )
  }
  if (data.status === "no_data") return null

  const stale = data.status === "stale"
  const top = sortBySeverity(data.insights ?? []).slice(0, TOP)
  const generated =
    data.status === "none" ? null : generatedLabel(data.generated_at)

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-baseline gap-3">
            <h2 className="text-base font-semibold">Insights</h2>
            {generated && (
              <span className="text-sm text-muted-foreground">{generated}</span>
            )}
          </div>
          <Link href="/insights" className={LINK}>
            View all
          </Link>
        </div>
        {stale && (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              {STALE_NOTE[data.stale_reason ?? "data_changed"]}
            </p>
            <Link href="/insights" className={LINK}>
              Refresh insights
            </Link>
          </div>
        )}
        {data.status === "none" ? (
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              Your insights haven&apos;t been written yet.
            </p>
            <Link href="/insights" className={LINK}>
              Open Insights
            </Link>
          </div>
        ) : top.length === 0 ? (
          <p className="text-sm text-muted-foreground">{NOTHING_STANDS_OUT}</p>
        ) : (
          <ul
            data-testid="callout-cards"
            className={stale ? "space-y-2 opacity-60" : "space-y-2"}
          >
            {top.map((insight, i) => (
              <li key={i} className="space-y-1">
                <InsightBadges
                  insight={insight}
                  showSection
                  showKeyFigure={false}
                  monthToDateThrough={data.month_to_date_through}
                />
                <p
                  data-testid="callout-summary"
                  className="text-sm font-medium"
                >
                  {insight.summary}
                </p>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  )
}
