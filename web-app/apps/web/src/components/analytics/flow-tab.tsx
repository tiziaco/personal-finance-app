"use client"

import {
  getGetDashboardQueryKey,
  useGetSpending,
} from "@app/api-client/endpoints/analytics"
import type { DashboardResponse, SpendingResponse } from "@app/api-client/types"
import { cn } from "@app/core/lib/utils"
import { Skeleton } from "@app/ui/skeleton"
import { useQueryClient } from "@tanstack/react-query"
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
  formatAmount,
  formatSignedAmount,
} from "@/components/transactions/format"

import {
  Change,
  SavingsHeadline,
  signedAmountClass,
  TONE_CLASS,
} from "./change"
import { FlowChart } from "./flow-chart"
import {
  changeTone,
  formatPct,
  partialLabel,
  type PartialLabel,
} from "./format"
import { monthToDate, toMonthPoints } from "./month-points"
import { MonthToDateStrip } from "./month-to-date-strip"
import { PeriodHeader } from "./period-select"
import { ANALYTICS_QUERY } from "./query"
import { QueryGate } from "./query-gate"
import { Section } from "./section"
import { PERIODS } from "./use-analytics-params"

const WHAT = "your income and expenses"
const EMPTY = "No transactions in this period."

const isEmpty = (data: SpendingResponse) => data.date_from === null

/** A net: signed, green when up, red when down. */
const netClass = (amount: string) => signedAmountClass(amount, "up")
const formatNet = (amount: string) => formatSignedAmount(amount)

function Figure({
  label,
  amount,
  average,
  signed,
}: {
  label: string
  amount: string
  /** Null when the period has no whole month to average over. */
  average: string | null
  /** A net: sign it, and colour it and its average good or bad. */
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
        {signed ? formatNet(amount) : formatAmount(amount)}
      </p>
      <p
        className={cn(
          "text-xs",
          (average !== null && signed && netClass(average)) ||
            "text-muted-foreground",
        )}
      >
        {average === null
          ? "No full month yet"
          : `${signed ? formatNet(average) : formatAmount(average)} / month`}
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
  // Before the first response, the cached dashboard says which blocks the
  // period will lack. The latest-month section is missing when the reference
  // month is the one in progress, or is the data's first month (a one-month
  // trend): a first month that starts after day 7 is not whole, and most do.
  // The strip is missing too when there is no month to date (same call as
  // spending's). With nothing cached, assume both are present.
  const dash = useQueryClient().getQueryData<DashboardResponse>(
    getGetDashboardQueryKey(),
  )
  const inProgress = dash?.reference_partial === true
  const noLatest = inProgress || dash?.monthly_trend.length === 1
  const noStrip = inProgress || dash?.month_to_date === null

  return (
    <div className="flex flex-col gap-6">
      <PeriodHeader
        choices={PERIODS.flow.choices}
        value={months}
        onChange={onMonthsChange}
        range={data}
        dimmed={query.isPlaceholderData}
      />

      <QueryGate
        query={query}
        what={WHAT}
        isEmpty={isEmpty}
        empty={EMPTY}
        skeleton={
          <>
            {/* Heights of the real blocks, measured with the seed data: the strip 142px while its lines wrap,
                else 102px; the latest-month card 184px stacked, 110px in two columns, 130px beside the sidebar. */}
            {noStrip ? null : (
              <Skeleton
                data-testid="mtd-skeleton"
                className="h-[142px] w-full sm:h-[102px]"
              />
            )}
            <Section title="Income and expenses">
              <Skeleton className="aspect-[2/1] w-full" />
            </Section>
            <Section title="Cash flow">
              <Skeleton className="h-32 w-full" />
            </Section>
            {noLatest ? null : (
              <Skeleton
                data-testid="latest-skeleton"
                className="h-[184px] w-full sm:h-[110px] md:h-[130px] lg:h-[110px]"
              />
            )}
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
                            {formatNet(m.net)}
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
                          <p className={netClass(m.net)}>{formatNet(m.net)}</p>
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
