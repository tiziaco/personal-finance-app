'use client'

import { ErrorBoundary } from '@/components/shared/error-boundary'
import { CardSkeleton } from '@/components/shared/skeletons/card-skeleton'
import { ChartSkeleton } from '@/components/shared/skeletons/chart-skeleton'
import { WelcomeCard } from '@/components/dashboard/welcome-card'
import { SummaryCards } from '@/components/dashboard/summary-cards'
import { SpendingPieChart } from '@/components/dashboard/spending-pie-chart'
import { TrendLineChart } from '@/components/dashboard/trend-line-chart'
import { RecentTransactions } from '@/components/dashboard/recent-transactions'
import { InsightsCallout } from '@/components/dashboard/insights-callout'

export default function HomePage() {
  return (
    <div className="space-y-6 p-0">
      <ErrorBoundary>
        <WelcomeCard />
      </ErrorBoundary>

      <ErrorBoundary fallback={<div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4"><CardSkeleton count={4} /></div>}>
        <SummaryCards />
      </ErrorBoundary>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <ErrorBoundary fallback={<ChartSkeleton variant="pie" />}>
          <SpendingPieChart />
        </ErrorBoundary>
        <ErrorBoundary fallback={<ChartSkeleton variant="line" />}>
          <TrendLineChart />
        </ErrorBoundary>
      </div>

      <ErrorBoundary>
        <RecentTransactions />
      </ErrorBoundary>

      <ErrorBoundary>
        <InsightsCallout />
      </ErrorBoundary>
    </div>
  )
}
