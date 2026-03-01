'use client'

import { useState } from 'react'
import { useCategoriesAnalytics } from '@/hooks/use-analytics'
import { PieChart } from '@/components/shared/charts/pie-chart'
import { ChartSkeleton } from '@/components/shared/skeletons/chart-skeleton'
import { ErrorBoundary } from '@/components/shared/error-boundary'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { formatCurrency, formatPercent } from '@/lib/format'
import type { ChartConfig } from '@/components/ui/chart'

// Inline type — narrows AnalyticsResponse.data for this endpoint
interface CategoryAnalyticsData {
  top_categories: Array<{
    category: string
    total_amount: number
    transaction_count: number
    percentage: number  // already-scaled percent (e.g. 45.6)
  }>
  frequency_vs_impact: Record<string, unknown>[]
  confidence_weighted: Record<string, unknown>[]
  category_trends: {
    top_growing: Record<string, unknown>[]
    top_declining: Record<string, unknown>[]
  }
}

type DateRange = '1M' | '3M' | '6M'

function getDateFrom(range: DateRange): string {
  const d = new Date()
  const months = range === '1M' ? 1 : range === '3M' ? 3 : 6
  d.setMonth(d.getMonth() - months)
  return d.toISOString().split('T')[0]  // "YYYY-MM-DD"
}

interface SpendingByCategoryTabProps {
  enabled: boolean
}

export function SpendingByCategoryTab({ enabled }: SpendingByCategoryTabProps) {
  const [range, setRange] = useState<DateRange>('3M')
  const dateFrom = getDateFrom(range)

  // CRITICAL: pass enabled — must NOT fire until tab is first activated
  const { data, isLoading } = useCategoriesAnalytics({ date_from: dateFrom }, enabled)

  if (isLoading) {
    return <ChartSkeleton variant="pie" />
  }

  const narrowed = data?.data as CategoryAnalyticsData | undefined
  const topCategories = narrowed?.top_categories ?? []

  const chartData = topCategories.map(c => ({ label: c.category, value: c.total_amount }))
  const config: ChartConfig = Object.fromEntries(
    topCategories.map((c, i) => [
      c.category,
      { label: c.category, color: `var(--chart-${(i % 5) + 1})` }  // var(--chart-N) directly — NOT hsl()
    ])
  )

  return (
    <div className="space-y-4">
      {/* Date range filter */}
      <div className="flex items-center gap-2">
        <span className="text-sm text-muted-foreground">Show:</span>
        {(['1M', '3M', '6M'] as const).map((r) => (
          <Button
            key={r}
            variant={range === r ? 'default' : 'outline'}
            size="sm"
            onClick={() => setRange(r)}
          >
            {r}
          </Button>
        ))}
      </div>

      {topCategories.length === 0 ? (
        <Card>
          <CardHeader><CardTitle>Spending by Category</CardTitle></CardHeader>
          <CardContent className="flex items-center justify-center h-48">
            <p className="text-sm text-muted-foreground">No spending data for this period</p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <ErrorBoundary>
            <Card>
              <CardHeader>
                <CardTitle>Spending by Category</CardTitle>
              </CardHeader>
              <CardContent>
                <PieChart data={chartData} config={config} showLegend />
              </CardContent>
            </Card>
          </ErrorBoundary>

          <Card>
            <CardHeader>
              <CardTitle>Category Breakdown</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {topCategories.map((c, i) => (
                  <div key={c.category} className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-2">
                      <span
                        className="inline-block h-3 w-3 rounded-full shrink-0"
                        style={{ backgroundColor: `var(--chart-${(i % 5) + 1})` }}
                      />
                      <span className="font-medium truncate max-w-40">{c.category}</span>
                    </div>
                    <div className="flex items-center gap-3 text-right">
                      <span className="text-muted-foreground">{formatPercent(c.percentage)}</span>
                      <span className="font-semibold">{formatCurrency(c.total_amount)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
