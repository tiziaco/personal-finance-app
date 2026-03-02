'use client'

import Link from 'next/link'
import { useInsights } from '@/hooks/use-insights'
import { useTransactions } from '@/hooks/use-transactions'
import { InsightCardSkeleton } from '@/components/shared/skeletons/insight-card-skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export function InsightsCallout() {
  const { data: insightsData, isLoading: isLoadingInsights } = useInsights()
  const { data: txnData, isLoading: isLoadingTxn } = useTransactions(
    { sort_by: 'date', sort_order: 'desc', limit: 1 },
    0
  )

  if (isLoadingInsights || isLoadingTxn) return <InsightCardSkeleton />

  const topInsights = insightsData?.insights?.slice(0, 2) ?? []

  // DASH-06: Show "New data" badge when the most recent transaction is newer than insights generation
  const isStale =
    !!insightsData?.generated_at &&
    !!txnData?.items?.[0]?.date &&
    new Date(txnData.items[0].date) > new Date(insightsData.generated_at)

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle>AI Insights</CardTitle>
        {isStale && (
          <Badge variant="destructive" className="text-xs shrink-0">New data</Badge>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {topInsights.length === 0 ? (
          // Empty state — no insights yet
          <div className="text-center py-4">
            <p className="text-sm text-muted-foreground mb-3">
              No insights yet. Upload a CSV to generate your first AI analysis.
            </p>
            {/* DASH-07: "Generate New Insights" button in empty state */}
            <Link
              href="/insights"
              className={cn(buttonVariants({ variant: 'default', size: 'sm' }))}
            >
              Generate New Insights
            </Link>
          </div>
        ) : (
          <>
            <div className="space-y-2">
              {topInsights.map((insight) => (
                <div key={insight.insight_id} className="bg-muted rounded-lg p-3">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <Badge variant="secondary" className="text-xs shrink-0">{insight.type}</Badge>
                    <span className={cn(
                      'text-xs',
                      ['high', 'critical'].includes(insight.severity)
                        ? 'text-destructive'
                        : 'text-muted-foreground'
                    )}>
                      {insight.severity}
                    </span>
                  </div>
                  <p className="text-sm font-medium">{insight.summary}</p>
                </div>
              ))}
            </div>
            {/* DASH-06: "Generate New Insights" also present in non-empty state */}
            <Link
              href="/insights"
              className={cn(buttonVariants({ variant: 'outline', size: 'sm' }), 'w-full')}
            >
              Generate New Insights
            </Link>
          </>
        )}

        {/* DASH-08: Upload CSV CTA always visible */}
        <div className="flex gap-3 pt-2">
          <Link
            href="/upload"
            className={cn(buttonVariants({ variant: 'default', size: 'sm' }))}
          >
            Upload CSV
          </Link>
          <Link
            href="/insights"
            className={cn(buttonVariants({ variant: 'outline', size: 'sm' }))}
          >
            View Insights
          </Link>
        </div>
      </CardContent>
    </Card>
  )
}
