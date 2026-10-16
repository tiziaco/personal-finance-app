"use client"

import { useEffect, useRef } from "react"
import Link from "next/link"
import { useIsMutating, useQueryClient } from "@tanstack/react-query"
import {
  getGenerateInsightsMutationKey,
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
 * Each staleness generates once: a set that is new or out of date runs `generate`
 * a single time, keyed by the stored set's `generated_at`. A failed run leaves
 * the key unchanged, so it cannot loop; Retry is the user's explicit second
 * attempt. A set that goes stale again after a success has a new key and runs
 * once more. While a run is in flight — one started before the page remounted
 * included — nothing starts: a second paid call would answer the same. If that
 * run fails, this mount makes its own single attempt.
 */
export function useGenerateOnArrival(
  staleKey: string | null,
  generate: () => void,
  inFlight: boolean,
) {
  const attempted = useRef<string | null>(null)
  useEffect(() => {
    if (staleKey === null || inFlight || attempted.current === staleKey) return
    attempted.current = staleKey
    generate()
  }, [staleKey, generate, inFlight])
}

const GENERATE_KEY = getGenerateInsightsMutationKey()

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
      mutationKey: GENERATE_KEY,
      // The page reports a failure itself, by the button or as a Retry card.
      meta: { silentError: true },
      onSuccess: (data: InsightsResponse) =>
        queryClient.setQueryData(getGetInsightsQueryKey(), data),
    },
  })
  // Counts runs from an earlier mount of this page too, which `generate` cannot see.
  const inFlight = useIsMutating({ mutationKey: GENERATE_KEY }) > 0
  const data = query.data
  const stale = data?.status === "none" || data?.status === "stale"
  const { mutate } = generate
  const run = () => mutate()

  useGenerateOnArrival(
    stale ? (data?.generated_at ?? "none") : null,
    run,
    inFlight,
  )

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
  // Working means a run is in flight, never merely that the set is stale: a stale
  // set the page has already tried (and failed) must not look busy.
  const working = generate.isPending || inFlight

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
      ) : working || (stale && !failed) ? (
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
