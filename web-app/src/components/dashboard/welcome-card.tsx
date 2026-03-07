'use client'

import { useUser } from '@clerk/nextjs'
import { useDashboardSummary } from '@/hooks/use-dashboard-summary'
import { CardSkeleton } from '@/components/shared/skeletons/card-skeleton'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { useFormatCurrency } from '@/hooks/use-currency-format'

export function WelcomeCard() {
  const { user } = useUser()
  const { data, isLoading } = useDashboardSummary()
  const formatCurrency = useFormatCurrency()

  if (isLoading) return <CardSkeleton />

  const latestStat = data?.spending.overview.stats.at(-1)
  const totalSpent = latestStat?.total_expense ?? 0

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-2xl">
          Welcome back, {user?.firstName ?? 'there'}
        </CardTitle>
        <CardDescription>
          {latestStat?.month
            ? `Your spending for ${latestStat.month}`
            : 'Your financial overview'}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <p className="text-4xl font-bold text-primary">{formatCurrency(totalSpent)}</p>
        <p className="text-sm text-muted-foreground mt-1">spent this month</p>
      </CardContent>
    </Card>
  )
}
