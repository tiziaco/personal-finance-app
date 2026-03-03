'use client'

import { useSpendingAnalytics } from '@/hooks/use-analytics'
import { LineChart } from '@/components/shared/charts/line-chart'
import { ChartSkeleton } from '@/components/shared/skeletons/chart-skeleton'
import { ErrorBoundary } from '@/components/shared/error-boundary'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { useFormatCurrency } from '@/hooks/use-currency-format'
import type { ChartConfig } from '@/components/ui/chart'

// Inline type — narrows AnalyticsResponse.data for /api/v1/analytics/spending (trends fields)
interface SpendingAnalyticsData {
  overview: {
    stats: Array<{
      month: string
      total_expense: number
      total_income: number
      net: number
      expense_mom_growth: number | null
    }>
    income_vs_expenses: Record<string, unknown>[]
  }
  recent_trend: {
    last_3_months: Array<{
      month: string
      total_expense: number
      total_income: number
      net: number
    }>
    burn_rate: Record<string, unknown>[]
  }
  date_range: { start: string | null; end: string | null; total_days: number }
}

interface TrendsTabProps {
  enabled: boolean
}

const chartConfig: ChartConfig = {
  total_expense: { label: 'Monthly Expenses', color: 'var(--chart-1)' }, // var(--chart-N) directly — NOT hsl()
}

export function TrendsTab({ enabled }: TrendsTabProps) {
  const formatCurrency = useFormatCurrency()
  // CRITICAL: pass enabled — must NOT fire until tab is first activated
  // queryKey: ['analytics', 'spending', {}] — shared with IncomeVsExpensesTab; React Query serves from cache
  const { data, isLoading } = useSpendingAnalytics({}, enabled)

  if (isLoading) {
    return <ChartSkeleton variant="line" />
  }

  const narrowed = data?.data as SpendingAnalyticsData | undefined
  const stats = narrowed?.overview.stats ?? []

  const chartData: Record<string, unknown>[] = stats.map(s => ({
    month: s.month,
    total_expense: s.total_expense,
  }))

  return (
    <div className="space-y-6">
      {stats.length === 0 ? (
        <Card>
          <CardHeader><CardTitle>Month-over-Month Trends</CardTitle></CardHeader>
          <CardContent className="flex items-center justify-center h-48">
            <p className="text-sm text-muted-foreground">No trend data yet</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <ErrorBoundary>
            <Card>
              <CardHeader>
                <CardTitle>Monthly Expense Trend</CardTitle>
              </CardHeader>
              <CardContent>
                <LineChart
                  data={chartData}
                  series={[
                    { dataKey: 'total_expense', label: 'Expenses', color: 'var(--chart-1)' },
                  ]}
                  xAxisKey="month"
                  config={chartConfig}
                  className="h-[300px] w-full"
                />
              </CardContent>
            </Card>
          </ErrorBoundary>

          {/* Month-over-month growth table */}
          <Card>
            <CardHeader>
              <CardTitle>Month-over-Month Growth</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {stats.map((s) => {
                  const growth = s.expense_mom_growth
                  return (
                    <div key={s.month} className="flex items-center justify-between text-sm py-2 border-t first:border-t-0">
                      <span className="font-medium text-muted-foreground">{s.month}</span>
                      <div className="flex items-center gap-6">
                        <span className="font-semibold">{formatCurrency(s.total_expense)}</span>
                        {growth !== null && growth !== undefined ? (
                          <span className={`text-xs font-medium w-16 text-right ${growth > 0 ? 'text-destructive' : 'text-success'}`}>
                            {growth > 0 ? '+' : ''}{growth.toFixed(1)}%
                          </span>
                        ) : (
                          <span className="text-xs text-muted-foreground w-16 text-right">—</span>
                        )}
                      </div>
                    </div>
                  )
                })}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
