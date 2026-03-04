'use client'

import { useInsights } from '@/hooks/use-insights'
import { GenerateButton } from '@/components/insights/generate-button'
import { InsightCategoryTabs } from '@/components/insights/insight-category-tabs'
import { SavingsTracker } from '@/components/insights/savings-tracker'
import { InsightsEmptyState } from '@/components/insights/insights-empty-state'
import { InsightCardSkeleton } from '@/components/shared/skeletons/insight-card-skeleton'
import { ErrorBoundary } from '@/components/shared/error-boundary'

export default function InsightsPage() {
  const { data: insightsData, isLoading, isFetching, refetch } = useInsights()

  const insights = insightsData?.insights ?? []
  const generatedAt = insightsData?.generated_at ?? ''

  // Empty state: fetched successfully but zero insights returned
  // isLoading = true during first fetch; isFetching = true during any fetch including refetch
  const isEmptyState = !isLoading && !isFetching && insights.length === 0

  return (
    <div className="container max-w-6xl mx-auto py-8 space-y-8">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold">AI Insights</h1>
          <p className="text-sm text-muted-foreground">
            AI-powered analysis of your spending patterns and savings opportunities
          </p>
        </div>
        {/* GenerateButton manages its own cooldown state internally */}
        <GenerateButton />
      </div>

      {isLoading && (
        <div className="space-y-4">
          <InsightCardSkeleton count={4} />
        </div>
      )}

      {isEmptyState && (
        <InsightsEmptyState
          onGenerate={() => refetch()}
          isGenerating={isFetching}
        />
      )}

      {!isLoading && insights.length > 0 && (
        <ErrorBoundary>
          <div className="space-y-8">
            <SavingsTracker insights={insights} />
            <InsightCategoryTabs insights={insights} generatedAt={generatedAt} />
          </div>
        </ErrorBoundary>
      )}
    </div>
  )
}
