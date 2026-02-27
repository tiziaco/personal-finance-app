'use client'

import { useDashboardSummary } from '@/hooks/use-dashboard-summary'
import { LineChart } from '@/components/shared/charts/line-chart'
import { ChartSkeleton } from '@/components/shared/skeletons/chart-skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

export function TrendLineChart() {
  const { data, isLoading } = useDashboardSummary()

  if (isLoading) return <ChartSkeleton variant="line" />

  const last6 = (data?.trends.monthly_trend ?? []).slice(-6)

  if (last6.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle>6-Month Spending Trend</CardTitle></CardHeader>
        <CardContent className="flex items-center justify-center h-48">
          <p className="text-sm text-muted-foreground">No trend data yet</p>
        </CardContent>
      </Card>
    )
  }

  const config = {
    total_expense: { label: 'Expenses', color: 'var(--chart-1)' },
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>6-Month Spending Trend</CardTitle>
      </CardHeader>
      <CardContent>
        <LineChart
          data={last6 as unknown as Record<string, unknown>[]}
          series={[{ dataKey: 'total_expense', color: 'var(--chart-1)', label: 'Expenses' }]}
          xAxisKey="month"
          config={config}
        />
      </CardContent>
    </Card>
  )
}
