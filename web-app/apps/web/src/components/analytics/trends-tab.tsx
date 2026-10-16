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

import { TONE_CLASS } from "./change"
import { CategoryMovers } from "./category-movers"
import { changeTone, formatPeriod, formatPct } from "./format"
import { PeriodSelect } from "./period-select"
import { ANALYTICS_QUERY } from "./query"
import { Section } from "./section"
import {
  MonthChangeChart,
  SavingsRateChart,
  SpendingTrendChart,
} from "./trends-charts"
import { toTrendsPoints } from "./trends-points"
import { PERIODS } from "./use-analytics-params"

const EMPTY = "No transactions in this period."
const CAPTION = "Earlier half vs later half of the period, per month"

const isEmpty = (data: SpendingResponse | CategoryBreakdownResponse) =>
  data.date_from === null

const chartSkeleton = <Skeleton className="aspect-[2/1] w-full" />

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
  const period =
    spending.data &&
    formatPeriod(spending.data.date_from, spending.data.date_to)
  const flow = {
    query: spending,
    what: "your spending trend",
    isEmpty,
    empty: EMPTY,
    skeleton: chartSkeleton,
  }
  const movers = {
    query: categories,
    what: "your category movers",
    isEmpty,
    empty: EMPTY,
    skeleton: <Skeleton className="h-32 w-full" />,
  }

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <PeriodSelect
          choices={PERIODS.trends.choices}
          value={months}
          onChange={onMonthsChange}
        />
        {period ? (
          <p className="text-sm text-muted-foreground">{period}</p>
        ) : null}
      </header>

      <Section {...flow} title="Spending trend">
        {(d) => (
          <SpendingTrendChart
            points={toTrendsPoints(d.months, d.month_to_date?.month)}
          />
        )}
      </Section>

      <Section {...flow} title="Month-over-month change">
        {(d) => (
          <MonthChangeChart
            points={toTrendsPoints(d.months, d.month_to_date?.month)}
          />
        )}
      </Section>

      <Section {...flow} title="Savings rate">
        {(d) => {
          const pct = d.savings_rate_pct
          const tone = pct === null ? null : changeTone(pct, "income")
          return (
            <div className="flex flex-col gap-3">
              <p className="text-lg font-semibold">
                {pct === null || tone === null ? (
                  "—"
                ) : (
                  <span data-tone={tone} className={TONE_CLASS[tone]}>
                    {`Kept ${formatPct(pct)} of income`}
                  </span>
                )}
              </p>
              <SavingsRateChart
                points={toTrendsPoints(d.months, d.month_to_date?.month)}
              />
            </div>
          )
        }}
      </Section>

      <Section {...movers} title="Growing">
        {(d) => (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">{CAPTION}</p>
            <CategoryMovers
              rows={d.top_growing}
              empty="No category grew between the two halves of the period."
            />
          </div>
        )}
      </Section>

      <Section {...movers} title="Declining">
        {(d) => (
          <div className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">{CAPTION}</p>
            <CategoryMovers
              rows={d.top_declining}
              empty="No category declined between the two halves of the period."
            />
          </div>
        )}
      </Section>
    </div>
  )
}
