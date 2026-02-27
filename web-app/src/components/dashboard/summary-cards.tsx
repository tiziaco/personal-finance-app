'use client'

import { CreditCard, RefreshCw, TrendingUp, TrendingDown, PiggyBank } from 'lucide-react'
import { useDashboardSummary } from '@/hooks/use-dashboard-summary'
import { CardSkeleton } from '@/components/shared/skeletons/card-skeleton'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCurrency } from '@/lib/format'
import { cn } from '@/lib/utils'

export function SummaryCards() {
  const { data, isLoading } = useDashboardSummary()

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <CardSkeleton count={4} />
      </div>
    )
  }

  const latestStat = data?.spending.overview.stats.at(-1)

  // 1. Total Spent This Month
  const totalSpent = latestStat?.total_expense ?? 0

  // 2. Recurring Costs
  const recurringPct = data?.recurring.insights.total_recurring_percentage ?? 0
  const recurringAmount = totalSpent * (recurringPct / 100)
  const isRecurringHigh = recurringPct > 40

  // 3. Net Balance (Cash Flow)
  const netBalance = latestStat?.net ?? 0
  const isNetNegative = netBalance < 0

  // 4. Savings — average of last 3 months' net
  const last3Months = data?.spending.recent_trend.last_3_months ?? []
  const avgSavings =
    last3Months.length > 0
      ? last3Months.reduce((sum, stat) => sum + stat.net, 0) / last3Months.length
      : 0
  const isSavingsNegative = avgSavings < 0

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {/* Card 1: Total Spent */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Total Spent</CardTitle>
          <CreditCard className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className={cn('text-2xl font-bold', 'text-primary')}>
            {formatCurrency(totalSpent)}
          </div>
          <p className="text-xs text-muted-foreground mt-1">this month</p>
        </CardContent>
      </Card>

      {/* Card 2: Recurring Costs */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Recurring Costs</CardTitle>
          <RefreshCw className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className={cn('text-2xl font-bold', isRecurringHigh ? 'text-destructive' : 'text-primary')}>
            {formatCurrency(recurringAmount)}
          </div>
          <p className="text-xs text-muted-foreground mt-1">monthly</p>
        </CardContent>
      </Card>

      {/* Card 3: Net Balance (Cash Flow) */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Net Balance</CardTitle>
          {isNetNegative
            ? <TrendingDown className="h-4 w-4 text-muted-foreground" />
            : <TrendingUp className="h-4 w-4 text-muted-foreground" />
          }
        </CardHeader>
        <CardContent>
          <div className={cn('text-2xl font-bold', isNetNegative ? 'text-destructive' : 'text-primary')}>
            {formatCurrency(netBalance)}
          </div>
          <p className="text-xs text-muted-foreground mt-1">Net this month</p>
        </CardContent>
      </Card>

      {/* Card 4: Savings */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">Savings</CardTitle>
          <PiggyBank className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className={cn('text-2xl font-bold', isSavingsNegative ? 'text-destructive' : 'text-primary')}>
            {formatCurrency(avgSavings)}
          </div>
          <p className="text-xs text-muted-foreground mt-1">Avg monthly savings (3mo)</p>
        </CardContent>
      </Card>
    </div>
  )
}
