"use client"

import { useCallback, useEffect, useRef } from "react"
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
import { SectionError } from "@/components/dashboard/section-error"
import { CardsSkeleton } from "./cards-skeleton"
import { InsightTabs } from "./insight-tabs"
import { InsightsHeader } from "./insights-header"
import { NOTHING_STANDS_OUT } from "./labels"

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

/** Stale-key stand-in for a set that was never generated (it has no `generated_at`). */
const NEVER_GENERATED = "none"

type Phase =
  | "loading"
  | "load_error"
  | "no_data"
  | "generating"
  | "failed"
  | "empty"
  | "cards"

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
  // Stable, so the arrival effect does not re-run every render. Called with no
  // arguments: an onClick must not pass the event on as mutation variables.
  const run = useCallback(() => mutate(), [mutate])

  useGenerateOnArrival(
    stale ? (data?.generated_at ?? NEVER_GENERATED) : null,
    run,
    inFlight,
  )

  const cards = data?.insights ?? []
  const failed = generate.isError
  // Working means a run is in flight, never merely that the set is stale: a stale
  // set the page has already tried (and failed) must not look busy.
  const working = generate.isPending || inFlight

  const phase: Phase = !data
    ? query.isError
      ? "load_error"
      : "loading"
    : data.status === "no_data"
      ? "no_data"
      : cards.length > 0
        ? "cards"
        : working || (stale && !failed)
          ? "generating"
          : failed
            ? "failed"
            : "empty"

  const header =
    data && phase !== "no_data" ? (
      <InsightsHeader
        generatedAt={data.generated_at}
        pending={working}
        error={failed && cards.length > 0}
        onRegenerate={run}
      />
    ) : (
      <InsightsHeader pending={false} error={false} />
    )

  return (
    <div className="space-y-6">
      {header}
      {phase === "loading" && <CardsSkeleton />}
      {phase === "load_error" && (
        <SectionError
          what="your insights"
          onRetry={() => void query.refetch()}
        />
      )}
      {phase === "no_data" && (
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
      )}
      {phase === "cards" && data && (
        <div className={working ? "opacity-60" : undefined} aria-busy={working}>
          <InsightTabs
            insights={cards}
            referenceMonth={data.reference_month}
            monthToDateThrough={data.month_to_date_through}
          />
        </div>
      )}
      {phase === "generating" && <CardsSkeleton />}
      {phase === "failed" && (
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
      )}
      {phase === "empty" && (
        <p className="text-sm text-muted-foreground">{NOTHING_STANDS_OUT}</p>
      )}
    </div>
  )
}
