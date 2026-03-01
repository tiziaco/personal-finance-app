'use client'

import { useSpendingAnalytics } from '@/hooks/use-analytics'
import { BarChart } from '@/components/shared/charts/bar-chart'
import { ChartSkeleton } from '@/components/shared/skeletons/chart-skeleton'
import { ErrorBoundary } from '@/components/shared/error-boundary'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCurrency } from '@/lib/format'
import type { ChartConfig } from '@/components/ui/chart'

// Inline type — narrows AnalyticsResponse.data for /api/v1/analytics/spending
interface SpendingAnalyticsData {
  overview: {
    stats: Array<{
      month: string         // "2026-02" format
      total_expense: number
      total_income: number
      net: number
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

interface IncomeVsExpensesTabProps {
  enabled: boolean
}

const chartConfig: ChartConfig = {
  total_income: { label: 'Income', color: 'var(--chart-2)' },   // var(--chart-N) directly — NOT hsl()
  total_expense: { label: 'Expenses', color: 'var(--chart-1)' },
}

export function IncomeVsExpensesTab({ enabled }: IncomeVsExpensesTabProps) {
  // CRITICAL: pass enabled — must NOT fire until tab is first activated
  // No date filters needed for this tab (research: no filter controls on income vs expenses)
  const { data, isLoading } = useSpendingAnalytics({}, enabled)

  if (isLoading) {
    return <ChartSkeleton variant="bar" />
  }

  const narrowed = data?.data as SpendingAnalyticsData | undefined
  // Use overview.stats[] — authoritative source per research open question #2
  const stats = narrowed?.overview.stats ?? []

  // Map to BarChart's expected Record<string, unknown>[] format
  const chartData: Record<string, unknown>[] = stats.map(s => ({
    month: s.month,
    total_income: s.total_income,
    total_expense: s.total_expense,
    net: s.net,
  }))

  const totalIncome = stats.reduce((sum, s) => sum + s.total_income, 0)
  const totalExpense = stats.reduce((sum, s) => sum + s.total_expense, 0)
  const totalNet = totalIncome - totalExpense

  return (
    <div className="space-y-6">
      {stats.length === 0 ? (
        <Card>
          <CardHeader><CardTitle>Income vs Expenses</CardTitle></CardHeader>
          <CardContent className="flex items-center justify-center h-48">
            <p className="text-sm text-muted-foreground">No income/expense data yet</p>
          </CardContent>
        </Card>
      ) : (
        <>
          <ErrorBoundary>
            <Card>
              <CardHeader>
                <CardTitle>Income vs Expenses by Month</CardTitle>
              </CardHeader>
              <CardContent>
                <BarChart
                  data={chartData}
                  series={[
                    { dataKey: 'total_income', label: 'Income', color: 'var(--chart-2)' },
                    { dataKey: 'total_expense', label: 'Expenses', color: 'var(--chart-1)' },
                  ]}
                  xAxisKey="month"
                  config={chartConfig}
                  className="h-[300px] w-full"
                />
              </CardContent>
            </Card>
          </ErrorBoundary>

          {/* Cash flow summary */}
          <Card>
            <CardHeader>
              <CardTitle>Cash Flow Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-3 gap-4 text-center">
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Total Income</p>
                  <p className="text-xl font-semibold text-green-600">{formatCurrency(totalIncome)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Total Expenses</p>
                  <p className="text-xl font-semibold text-destructive">{formatCurrency(totalExpense)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Net Cash Flow</p>
                  <p className={`text-xl font-semibold ${totalNet >= 0 ? 'text-green-600' : 'text-destructive'}`}>
                    {formatCurrency(totalNet)}
                  </p>
                </div>
              </div>

              {/* Monthly breakdown table */}
              <div className="mt-4 space-y-2">
                {stats.map(s => (
                  <div key={s.month} className="flex items-center justify-between text-sm py-2 border-t first:border-t-0">
                    <span className="font-medium text-muted-foreground">{s.month}</span>
                    <div className="flex items-center gap-6">
                      <span className="text-green-600">{formatCurrency(s.total_income)}</span>
                      <span className="text-destructive">{formatCurrency(s.total_expense)}</span>
                      <span className={`font-semibold w-24 text-right ${s.net >= 0 ? 'text-green-600' : 'text-destructive'}`}>
                        {formatCurrency(s.net)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  )
}
