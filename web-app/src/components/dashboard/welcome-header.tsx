'use client'

import { useUser } from '@clerk/nextjs'
import { useDashboardSummary } from '@/hooks/use-dashboard-summary'

export function WelcomeHeader() {
  const { user } = useUser()
  const { data } = useDashboardSummary()

  const latestStat = data?.spending.overview.stats.at(-1)

  return (
    <div>
      <h1 className="text-2xl font-bold">Welcome back, {user?.firstName ?? 'there'}</h1>
      <p className="text-sm text-muted-foreground">
        {latestStat?.month ? `Your financial overview for ${latestStat.month}` : 'Your financial overview'}
      </p>
    </div>
  )
}
