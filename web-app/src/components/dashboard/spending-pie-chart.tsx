'use client'

import { useDashboardSummary } from '@/hooks/use-dashboard-summary'
import { PieChart } from '@/components/shared/charts/pie-chart'
import { ChartSkeleton } from '@/components/shared/skeletons/chart-skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { ChartConfig } from '@/components/ui/chart'

export function SpendingPieChart() {
  const { data, isLoading } = useDashboardSummary()

  if (isLoading) return <ChartSkeleton variant="pie" />

  const top5 = data?.categories.top_categories.slice(0, 5) ?? []

  if (top5.length === 0) {
    return (
      <Card>
        <CardHeader><CardTitle>Spending by Category</CardTitle></CardHeader>
        <CardContent className="flex items-center justify-center h-48">
          <p className="text-sm text-muted-foreground">No spending data yet</p>
        </CardContent>
      </Card>
    )
  }

  const chartData = top5.map(c => ({ label: c.category, value: c.total_amount }))
  const config: ChartConfig = Object.fromEntries(
    top5.map((c, i) => [c.category, { label: c.category, color: `var(--chart-${(i % 5) + 1})` }])
  )

  return (
    <Card>
      <CardHeader>
        <CardTitle>Spending by Category</CardTitle>
      </CardHeader>
      <CardContent>
        <PieChart data={chartData} config={config} showLegend />
      </CardContent>
    </Card>
  )
}
