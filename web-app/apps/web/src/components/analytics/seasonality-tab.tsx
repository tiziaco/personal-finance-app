"use client"

import { useGetBehaviour } from "@app/api-client/endpoints/analytics"
import type { BehaviourResponse } from "@app/api-client/types"
import { Skeleton } from "@app/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@app/ui/table"

import { formatAmount } from "@/components/transactions/format"

import { formatPct, formatPeriod, purchases } from "./format"
import { ANALYTICS_QUERY } from "./query"
import { Section } from "./section"
import { MonthOfYearChart, WeekdayChart } from "./seasonality-charts"
import { toMonthOfYearPoints, toWeekdayPoints } from "./seasonality-points"

const isEmpty = (data: BehaviourResponse) => data.date_from === null

function biasSentence(bias: number | null) {
  if (bias === null) return null
  if (bias === 0) return "Weekend and weekday days cost the same"
  return `Weekend days cost you ${formatPct(Math.abs(bias))} ${bias > 0 ? "more" : "less"} than weekdays`
}

/** Spending by day of week, weekdays vs weekend and month of year, over all history. */
export function SeasonalityTab() {
  const query = useGetBehaviour(undefined, ANALYTICS_QUERY)
  const period =
    query.data && formatPeriod(query.data.date_from, query.data.date_to)
  const shared = {
    query,
    what: "your seasonality",
    isEmpty,
    empty: "No spending yet.",
    skeleton: <Skeleton className="aspect-[2/1] w-full" />,
  }

  return (
    <div className="flex flex-col gap-6">
      {period ? (
        <p className="text-sm text-muted-foreground">Based on {period}</p>
      ) : null}

      <Section {...shared} title="Average spend per day, by day of week">
        {(d) => {
          const points = toWeekdayPoints(d.by_weekday)
          return (
            <div className="flex flex-col gap-4">
              <WeekdayChart points={points} />
              <Table className="hidden sm:table">
                <TableHeader>
                  <TableRow>
                    <TableHead>Day</TableHead>
                    <TableHead className="text-right">Per day</TableHead>
                    <TableHead className="text-right">Purchases</TableHead>
                    <TableHead className="text-right">
                      Average purchase
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {points.map((p) => (
                    <TableRow key={p.name}>
                      <TableCell>{p.name}</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {p.perDayText}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {p.count}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {p.averageText}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <ul className="flex flex-col gap-3 sm:hidden">
                {points.map((p) => (
                  <li key={p.name} className="flex justify-between gap-3">
                    <div className="min-w-0">
                      <p className="truncate font-medium">{p.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {purchases(p.count)} · {p.averageText} average
                      </p>
                    </div>
                    <span className="tabular-nums">{p.perDayText} per day</span>
                  </li>
                ))}
              </ul>
            </div>
          )
        }}
      </Section>

      <Section
        {...shared}
        skeleton={<Skeleton className="h-20 w-full" />}
        title="Weekdays vs weekend"
      >
        {(d) => {
          const sentence = biasSentence(d.weekend_bias_pct)
          return (
            <div className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-4">
                {(
                  [
                    ["Weekdays", d.weekday.per_day],
                    ["Weekend", d.weekend.per_day],
                  ] as const
                ).map(([label, perDay]) => (
                  <div key={label}>
                    <p className="text-sm text-muted-foreground">{label}</p>
                    <p className="text-lg font-semibold tabular-nums">
                      {formatAmount(perDay)}
                    </p>
                    <p className="text-xs text-muted-foreground">per day</p>
                  </div>
                ))}
              </div>
              {sentence ? <p className="text-sm">{sentence}</p> : null}
            </div>
          )
        }}
      </Section>

      <Section {...shared} title="Average spend by month of year">
        {(d) => (
          <MonthOfYearChart points={toMonthOfYearPoints(d.seasonality)} />
        )}
      </Section>
    </div>
  )
}
