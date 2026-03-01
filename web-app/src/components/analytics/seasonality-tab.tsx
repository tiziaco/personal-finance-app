'use client'

import { useBehaviorAnalytics } from '@/hooks/use-analytics'
import { BarChart } from '@/components/shared/charts/bar-chart'
import { ChartSkeleton } from '@/components/shared/skeletons/chart-skeleton'
import { ErrorBoundary } from '@/components/shared/error-boundary'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ChartConfig } from '@/components/ui/chart'

// Inline type — narrows AnalyticsResponse.data for /api/v1/analytics/behavior
// NOTE: monthly_patterns field names beyond 'month' are partially unverified — access defensively
interface BehaviorAnalyticsData {
  day_of_week: {
    by_weekday: Array<{
      weekday: number
      day_name: string
      total_spending: number
      avg_transaction: number
      transaction_count: number
      percentage: number
    }>
    weekday_vs_weekend: Array<{
      day_type: string
      total_spending: number
      avg_per_day: number
    }>
    weekend_bias_percentage: number | null
  }
  seasonality: {
    monthly_patterns: Array<Record<string, unknown>> // typed loosely — field names partially unverified
    quarterly_patterns: Record<string, unknown>[]
  }
  volatility: {
    stable_categories: Record<string, unknown>[]
    volatile_categories: Record<string, unknown>[]
  }
  insights: {
    weekend_spender: boolean
    most_stable_category: string | null
    most_volatile_category: string | null
  }
}

const MONTH_NAMES = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

interface SeasonalityTabProps {
  enabled: boolean
}

const dayOfWeekConfig: ChartConfig = {
  total_spending: { label: 'Total Spending', color: 'var(--chart-3)' }, // var(--chart-N) directly — NOT hsl()
}

const monthlyConfig: ChartConfig = {
  spending: { label: 'Spending', color: 'var(--chart-4)' },
}

export function SeasonalityTab({ enabled }: SeasonalityTabProps) {
  // CRITICAL: pass enabled — must NOT fire until tab is first activated
  const { data, isLoading } = useBehaviorAnalytics({}, enabled)

  if (isLoading) {
    return (
      <div className="space-y-6">
        <ChartSkeleton variant="bar" />
        <ChartSkeleton variant="bar" />
      </div>
    )
  }

  const narrowed = data?.data as BehaviorAnalyticsData | undefined
  const byWeekday = narrowed?.day_of_week.by_weekday ?? []
  const monthlyPatterns = narrowed?.seasonality.monthly_patterns ?? []
  const insights = narrowed?.insights

  // Map weekday data to BarChart format
  const weekdayChartData: Record<string, unknown>[] = byWeekday.map(d => ({
    day_name: d.day_name,
    total_spending: d.total_spending,
  }))

  // Map monthly patterns — defensive access since field names are partially unverified
  // Try 'avg_spending' then 'total_spending' as fallback field names
  const monthlyChartData: Record<string, unknown>[] = monthlyPatterns.map(p => {
    const monthNum = p['month'] as number | undefined
    const spending = (p['avg_spending'] ?? p['total_spending'] ?? p['average_spending'] ?? 0) as number
    return {
      month_name: monthNum ? MONTH_NAMES[(monthNum - 1) % 12] : '?',
      spending,
    }
  })

  const hasWeekdayData = byWeekday.length > 0
  const hasMonthlyData = monthlyChartData.length > 0

  if (!hasWeekdayData && !hasMonthlyData) {
    return (
      <Card>
        <CardHeader><CardTitle>Seasonality</CardTitle></CardHeader>
        <CardContent className="flex items-center justify-center h-48">
          <p className="text-sm text-muted-foreground">No seasonality data yet</p>
        </CardContent>
      </Card>
    )
  }

  return (
    <div className="space-y-6">
      {/* Day of week spending pattern */}
      {hasWeekdayData && (
        <ErrorBoundary>
          <Card>
            <CardHeader>
              <CardTitle>Spending by Day of Week</CardTitle>
            </CardHeader>
            <CardContent>
              <BarChart
                data={weekdayChartData}
                series={[{ dataKey: 'total_spending', label: 'Total Spending', color: 'var(--chart-3)' }]}
                xAxisKey="day_name"
                config={dayOfWeekConfig}
                className="h-[280px] w-full"
              />
              {insights?.weekend_spender !== undefined && (
                <p className="text-sm text-muted-foreground mt-3">
                  {insights.weekend_spender
                    ? 'You tend to spend more on weekends.'
                    : 'Your spending is higher on weekdays.'}
                </p>
              )}
            </CardContent>
          </Card>
        </ErrorBoundary>
      )}

      {/* Monthly seasonality pattern */}
      {hasMonthlyData && (
        <ErrorBoundary>
          <Card>
            <CardHeader>
              <CardTitle>Spending by Month of Year</CardTitle>
            </CardHeader>
            <CardContent>
              <BarChart
                data={monthlyChartData}
                series={[{ dataKey: 'spending', label: 'Spending', color: 'var(--chart-4)' }]}
                xAxisKey="month_name"
                config={monthlyConfig}
                className="h-[280px] w-full"
              />
            </CardContent>
          </Card>
        </ErrorBoundary>
      )}
    </div>
  )
}
