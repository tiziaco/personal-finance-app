"use client"

import {
  useGetCategoryBreakdown,
  useGetSpending,
} from "@app/api-client/endpoints/analytics"
import type {
  CategoryBreakdownResponse,
  SpendingResponse,
} from "@app/api-client/types"
import { Skeleton } from "@app/ui/skeleton"

import { CategoryMovers } from "./category-movers"
import { SavingsHeadline } from "./change"
import { toMonthPoints } from "./month-points"
import { PeriodHeader } from "./period-select"
import { ANALYTICS_QUERY } from "./query"
import { QueryGate } from "./query-gate"
import { Section } from "./section"
import {
  MonthChangeChart,
  SavingsRateChart,
  SpendingTrendChart,
} from "./trends-charts"
import { PERIODS } from "./use-analytics-params"

const EMPTY = "No transactions in this period."
const CAPTION = "Earlier half vs later half of the period, per month"

const isEmpty = (data: SpendingResponse) => data.date_from === null

/** No period, or neither list has a mover. */
const moversEmpty = (data: CategoryBreakdownResponse) =>
  data.date_from === null ||
  (data.top_growing.length === 0 && data.top_declining.length === 0)

/** Why there are no movers: no period at all, or too short a period to compare. */
function moversEmptyNode(data: CategoryBreakdownResponse) {
  if (data.date_from === null) return EMPTY
  return (
    <div className="flex flex-col gap-1">
      <p>No category grew or declined between the two halves of the period.</p>
      <p className="text-xs">Needs at least two whole months.</p>
    </div>
  )
}

export function TrendsTab({
  months,
  onMonthsChange,
}: {
  months: number
  onMonthsChange: (months: number) => void
}) {
  const spending = useGetSpending({ months }, ANALYTICS_QUERY)
  const categories = useGetCategoryBreakdown(
    { months, top_n: 1 },
    ANALYTICS_QUERY,
  )
  return (
    <div className="flex flex-col gap-6">
      <PeriodHeader
        choices={PERIODS.trends.choices}
        value={months}
        onChange={onMonthsChange}
        range={spending.data}
        dimmed={spending.isPlaceholderData}
      />

      <QueryGate
        query={spending}
        what="your spending trend"
        isEmpty={isEmpty}
        empty={EMPTY}
        skeleton={
          <>
            <Section title="Spending trend">
              <Skeleton className="aspect-[2/1] w-full" />
            </Section>
            <Section title="Month-over-month change">
              <Skeleton className="aspect-[2/1] w-full" />
            </Section>
            <Section title="Savings rate">
              <Skeleton className="aspect-[2/1] w-full" />
            </Section>
          </>
        }
      >
        {(d) => {
          const points = toMonthPoints(d.months, d.month_to_date?.month)
          return (
            <>
              <Section title="Spending trend">
                <SpendingTrendChart points={points} />
              </Section>

              <Section title="Month-over-month change">
                {points.every((p) => p.change === null) ? (
                  <p className="text-sm text-muted-foreground">
                    Needs at least two months to compare.
                  </p>
                ) : (
                  <MonthChangeChart points={points} />
                )}
              </Section>

              <Section title="Savings rate">
                <div className="flex flex-col gap-3">
                  <p className="text-lg font-semibold">
                    <SavingsHeadline pct={d.savings_rate_pct} />
                  </p>
                  {points.every((p) => p.savingsRate === null) ? (
                    <p className="text-sm text-muted-foreground">
                      No month with income yet.
                    </p>
                  ) : (
                    <SavingsRateChart points={points} />
                  )}
                </div>
              </Section>
            </>
          )
        }}
      </QueryGate>

      <QueryGate
        query={categories}
        what="your category movers"
        isEmpty={moversEmpty}
        empty={moversEmptyNode}
        skeleton={
          <>
            <Section title="Growing">
              <Skeleton className="h-32 w-full" />
            </Section>
            <Section title="Declining">
              <Skeleton className="h-32 w-full" />
            </Section>
          </>
        }
      >
        {(d) => (
          <>
            <Section title="Growing">
              <div className="flex flex-col gap-3">
                <p className="text-sm text-muted-foreground">{CAPTION}</p>
                <CategoryMovers
                  rows={d.top_growing}
                  empty="No category grew between the two halves of the period."
                />
              </div>
            </Section>

            <Section title="Declining">
              <div className="flex flex-col gap-3">
                <p className="text-sm text-muted-foreground">{CAPTION}</p>
                <CategoryMovers
                  rows={d.top_declining}
                  empty="No category declined between the two halves of the period."
                />
              </div>
            </Section>
          </>
        )}
      </QueryGate>
    </div>
  )
}
