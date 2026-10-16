"use client"

import { useGetSpending } from "@app/api-client/endpoints/analytics"
import type { SpendingResponse } from "@app/api-client/types"
import { cn } from "@app/core/lib/utils"
import { Skeleton } from "@app/ui/skeleton"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@app/ui/table"

import { formatMonth } from "@/components/dashboard/month"
import {
  amountClass,
  formatAmount,
  isExpense,
} from "@/components/transactions/format"

import { Change, SavingsHeadline, TONE_CLASS } from "./change"
import { FlowChart } from "./flow-chart"
import {
  changeTone,
  formatPeriod,
  formatPct,
  partialLabel,
  type PartialLabel,
} from "./format"
import { monthToDate, toMonthPoints } from "./month-points"
import { MonthToDateStrip } from "./month-to-date-strip"
import { PeriodSelect } from "./period-select"
import { ANALYTICS_QUERY } from "./query"
import { QueryGate } from "./query-gate"
import { Section } from "./section"
import { PERIODS } from "./use-analytics-params"

const WHAT = "your income and expenses"
const EMPTY = "No transactions in this period."

const isEmpty = (data: SpendingResponse) => data.date_from === null

/** Red when negative; a positive amount keeps the text colour. */
const netClass = (amount: string) =>
  isExpense(amount) ? amountClass(amount) : ""

function Figure({
  label,
  amount,
  average,
  signed,
}: {
  label: string
  amount: string
  average: string
  /** Colour a negative amount and a negative average as bad. */
  signed?: boolean
}) {
  return (
    <div>
      <p className="text-sm text-muted-foreground">{label}</p>
      <p
        className={cn(
          "text-2xl font-semibold tabular-nums",
          signed && netClass(amount),
        )}
      >
        {formatAmount(amount)}
      </p>
      <p
        className={cn(
          "text-xs",
          signed && isExpense(average)
            ? amountClass(average)
            : "text-muted-foreground",
        )}
      >
        {`${formatAmount(average)} / month`}
      </p>
    </div>
  )
}

/** " · so far" or " · partial" after a month's name; nothing for a whole month. */
function PartialTag({
  label,
  className,
}: {
  label: PartialLabel | null
  className: string
}) {
  return label ? <span className={className}>{` · ${label}`}</span> : null
}

export function FlowTab({
  months,
  onMonthsChange,
}: {
  months: number
  onMonthsChange: (months: number) => void
}) {
  const query = useGetSpending({ months }, ANALYTICS_QUERY)
  const data = query.data
  const period = data && formatPeriod(data.date_from, data.date_to)

  return (
    <div className="flex flex-col gap-6">
      <header className="flex flex-col gap-3">
        <PeriodSelect
          choices={PERIODS.flow.choices}
          value={months}
          onChange={onMonthsChange}
        />
        {period ? (
          <p className="text-sm text-muted-foreground">{period}</p>
        ) : null}
      </header>

      <QueryGate
        query={query}
        what={WHAT}
        isEmpty={isEmpty}
        empty={EMPTY}
        skeleton={
          <>
            <Section title="Income and expenses">
              <Skeleton className="aspect-[2/1] w-full" />
            </Section>
            <Section title="Cash flow">
              <Skeleton className="h-32 w-full" />
            </Section>
            <Section title="Month by month">
              <Skeleton className="h-40 w-full" />
            </Section>
          </>
        }
      >
        {(d) => {
          const latest = d.latest_month
          const mtd = monthToDate(d)
          return (
            <>
              {mtd ? <MonthToDateStrip data={mtd} /> : null}

              <Section title="Income and expenses">
                <FlowChart
                  points={toMonthPoints(d.months, d.month_to_date?.month)}
                />
              </Section>

              <Section title="Cash flow">
                <div className="flex flex-col gap-4">
                  <div className="grid gap-4 sm:grid-cols-3">
                    <Figure
                      label="Income"
                      amount={d.total_income}
                      average={d.average_monthly_income}
                    />
                    <Figure
                      label="Expenses"
                      amount={d.total_expenses}
                      average={d.average_monthly_expenses}
                    />
                    <Figure
                      label="Net"
                      amount={d.net}
                      average={d.average_monthly_net}
                      signed
                    />
                  </div>
                  <p className="text-sm">
                    <SavingsHeadline pct={d.savings_rate_pct} />
                  </p>
                </div>
              </Section>

              {latest ? (
                <Section
                  title={`${formatMonth(latest.month)} vs the period average`}
                >
                  <dl className="grid gap-3 sm:grid-cols-2">
                    <div>
                      <dt className="text-sm text-muted-foreground">Income</dt>
                      <dd className="tabular-nums">
                        {formatAmount(latest.income)}{" "}
                        <Change
                          pct={latest.income_vs_average_pct}
                          kind="income"
                          up="above average"
                          down="below average"
                        />
                      </dd>
                    </div>
                    <div>
                      <dt className="text-sm text-muted-foreground">
                        Expenses
                      </dt>
                      <dd className="tabular-nums">
                        {formatAmount(latest.expenses)}{" "}
                        <Change
                          pct={latest.expenses_vs_average_pct}
                          kind="spend"
                          up="above average"
                          down="below average"
                        />
                      </dd>
                    </div>
                  </dl>
                </Section>
              ) : null}

              <Section title="Month by month">
                <>
                  <Table className="hidden sm:table">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Month</TableHead>
                        <TableHead className="text-right">Income</TableHead>
                        <TableHead className="text-right">Expenses</TableHead>
                        <TableHead className="text-right">Net</TableHead>
                        <TableHead className="text-right">
                          Savings rate
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {d.months.map((m) => (
                        <TableRow key={m.month}>
                          <TableCell>
                            {formatMonth(m.month)}
                            <PartialTag
                              label={partialLabel(
                                m.partial,
                                m.month,
                                d.month_to_date?.month,
                              )}
                              className="text-muted-foreground"
                            />
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {formatAmount(m.income)}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            {formatAmount(m.expenses)}
                          </TableCell>
                          <TableCell
                            className={`text-right tabular-nums ${netClass(m.net)}`}
                          >
                            {formatAmount(m.net)}
                          </TableCell>
                          <TableCell className="text-right tabular-nums">
                            <Rate pct={m.savings_rate_pct} />
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  <ul className="flex flex-col gap-3 sm:hidden">
                    {d.months.map((m) => (
                      <li key={m.month} className="flex justify-between gap-3">
                        <div className="min-w-0">
                          <p className="font-medium">
                            {formatMonth(m.month)}
                            <PartialTag
                              label={partialLabel(
                                m.partial,
                                m.month,
                                d.month_to_date?.month,
                              )}
                              className="text-xs font-normal text-muted-foreground"
                            />
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {formatAmount(m.income)} in ·{" "}
                            {formatAmount(m.expenses)} out
                          </p>
                        </div>
                        <div className="text-right tabular-nums">
                          <p className={netClass(m.net)}>
                            {formatAmount(m.net)}
                          </p>
                          <p className="text-xs">
                            <Rate pct={m.savings_rate_pct} />
                          </p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </>
              </Section>
            </>
          )
        }}
      </QueryGate>
    </div>
  )
}

/** A month's savings rate; bad when negative, a dash when there is none. */
function Rate({ pct }: { pct: number | null }) {
  if (pct === null) return <>—</>
  const tone = changeTone(pct, "income")
  return (
    <span data-tone={tone} className={TONE_CLASS[tone]}>
      {formatPct(pct)}
    </span>
  )
}
