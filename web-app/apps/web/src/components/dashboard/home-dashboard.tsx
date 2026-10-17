"use client"

import { useGetDashboard } from "@app/api-client/endpoints/analytics"
import { CategoryChart } from "./category-chart"
import { DashboardSkeleton } from "./dashboard-skeleton"
import { EmptyDashboard } from "./empty-dashboard"
import { InsightsCallout } from "./insights-callout"
import { MonthToDateCard } from "./month-to-date-card"
import { RecentTransactions } from "./recent-transactions"
import { SectionError } from "./section-error"
import { SummaryCards } from "./summary-cards"
import { TrendChart } from "./trend-chart"
import { WelcomeHeader } from "./welcome-header"

/** Analytics are costlier than a list; any transaction write invalidates them sooner (use-invalidate-transactions). */
export const ANALYTICS_STALE_TIME = 2 * 60 * 1000

export function HomeDashboard() {
  const query = useGetDashboard({
    query: { staleTime: ANALYTICS_STALE_TIME, meta: { silentError: true } },
  })
  const data = query.data

  if (data && data.reference_month === null) {
    return (
      <div className="space-y-6">
        <WelcomeHeader referenceMonth={null} />
        <EmptyDashboard />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <WelcomeHeader referenceMonth={data?.reference_month} />
      {/* A failed background refetch keeps its data: the error replaces only an empty section. */}
      {!data ? (
        query.isError ? (
          <SectionError
            what="your overview"
            onRetry={() => void query.refetch()}
          />
        ) : (
          <DashboardSkeleton />
        )
      ) : (
        <>
          {/* In a first month the reference month is the month in progress: the card would repeat it. */}
          {data.month_to_date && !data.reference_partial ? (
            <div className="grid gap-4 lg:grid-cols-[1fr_2fr]">
              <MonthToDateCard monthToDate={data.month_to_date} />
              <SummaryCards
                dashboard={data}
                className="content-start md:grid-cols-2"
              />
            </div>
          ) : (
            <SummaryCards dashboard={data} />
          )}
          <div className="grid gap-4 lg:grid-cols-2">
            <CategoryChart slices={data.spending_by_category} />
            <TrendChart points={data.monthly_trend} />
          </div>
          <InsightsCallout />
        </>
      )}
      <RecentTransactions />
    </div>
  )
}
