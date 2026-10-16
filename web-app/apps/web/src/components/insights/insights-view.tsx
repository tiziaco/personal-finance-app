"use client"

import { useEffect, useRef } from "react"
import Link from "next/link"
import { useQueryClient } from "@tanstack/react-query"
import {
  getGetInsightsQueryKey,
  useGenerateInsights,
  useGetInsights,
} from "@app/api-client/endpoints/insights"
import type { InsightsResponse } from "@app/api-client/types"
import { Button } from "@app/ui/button"
import { Card, CardContent } from "@app/ui/card"
import { Skeleton } from "@app/ui/skeleton"
import { SectionError } from "@/components/dashboard/section-error"
import { InsightTabs } from "./insight-tabs"
import { InsightsHeader } from "./insights-header"

/**
 * A new or out-of-date set generates once per mount. A ref guards it: a failed
 * run must not loop, and Retry is the user's explicit second attempt.
 */
export function useGenerateOnArrival(needed: boolean, generate: () => void) {
  const fired = useRef(false)
  useEffect(() => {
    if (!needed || fired.current) return
    fired.current = true
    generate()
  }, [needed, generate])
}

function CardsSkeleton() {
  return (
    <div className="space-y-3">
      {Array.from({ length: 3 }, (_, i) => (
        <Skeleton key={i} className="h-28 w-full" />
      ))}
    </div>
  )
}

export function InsightsView() {
  const queryClient = useQueryClient()
  const query = useGetInsights({ query: { meta: { silentError: true } } })
  const generate = useGenerateInsights({
    mutation: {
      onSuccess: (data: InsightsResponse) =>
        queryClient.setQueryData(getGetInsightsQueryKey(), data),
    },
  })
  const data = query.data
  const stale = data?.status === "none" || data?.status === "stale"
  const { mutate } = generate
  const run = () => mutate()

  useGenerateOnArrival(stale, run)

  if (!data) {
    return (
      <div className="space-y-6">
        <InsightsHeader pending={false} error={false} />
        {query.isError ? (
          <SectionError
            what="your insights"
            onRetry={() => void query.refetch()}
          />
        ) : (
          <CardsSkeleton />
        )}
      </div>
    )
  }

  if (data.status === "no_data") {
    return (
      <div className="space-y-6">
        <InsightsHeader pending={false} error={false} />
        <Card>
          <CardContent className="flex flex-wrap items-center justify-between gap-4">
            <p className="text-sm text-muted-foreground">
              Insights appear once you have transactions to look at.
            </p>
            <Link
              href="/transactions"
              className="text-sm underline underline-offset-4"
            >
              Upload a CSV
            </Link>
          </CardContent>
        </Card>
      </div>
    )
  }

  const cards = data.insights ?? []
  const failed = generate.isError
  // Until the arrival run starts (or after it fails) the stored set is shown as is.
  const working = generate.isPending || (stale && !failed)

  return (
    <div className="space-y-6">
      <InsightsHeader
        generatedAt={data.generated_at}
        pending={working}
        error={failed && cards.length > 0}
        onRegenerate={run}
      />
      {cards.length > 0 ? (
        <div className={working ? "opacity-60" : undefined} aria-busy={working}>
          <InsightTabs
            insights={cards}
            referenceMonth={data.reference_month}
            monthToDateThrough={data.month_to_date_through}
          />
        </div>
      ) : working ? (
        <CardsSkeleton />
      ) : failed ? (
        <Card>
          <CardContent className="flex items-center justify-between gap-4">
            <p className="text-sm text-muted-foreground">
              Couldn&apos;t generate your insights.
            </p>
            <Button variant="outline" size="sm" onClick={run}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : (
        <p className="text-sm text-muted-foreground">
          Nothing stands out this month.
        </p>
      )}
    </div>
  )
}
