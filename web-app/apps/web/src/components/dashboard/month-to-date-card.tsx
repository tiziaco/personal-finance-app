import { useId } from "react"
import type { MonthToDateResponse } from "@app/api-client/types"
import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"
import { parseIsoDay } from "@app/core/lib/dates"
import { formatAmount, formatPercent } from "@/components/transactions/format"
import { formatMonth } from "./month"

/** "+12%" / "−5%" / "0%": the card shows a whole percent (the insight chips keep a decimal below 10). */
const formatPct = (pct: number) =>
  formatPercent(pct, { decimals: "whole", unsignedZero: true })

/** "+12% vs €1,057", or null when the server sends no change. */
const formatChange = (pct: number | null, previous: string) =>
  pct === null ? null : `${formatPct(pct)} vs ${formatAmount(previous)}`

/** The month in progress, from day 1 to its last transaction, against the same days of the month before. */
export function MonthToDateCard({
  monthToDate,
}: {
  monthToDate: MonthToDateResponse
}) {
  const id = useId()
  const through = parseIsoDay(monthToDate.through)
  const day = through?.getDate() ?? 0
  const daysInMonth = through
    ? new Date(through.getFullYear(), through.getMonth() + 1, 0).getDate()
    : 0
  // The server's window: through the 31st compares with 1–30 Sep.
  const previousDay = parseIsoDay(monthToDate.previous_through)?.getDate() ?? 0
  const monthName = through
    ? new Intl.DateTimeFormat(undefined, { month: "long" }).format(through)
    : formatMonth(monthToDate.month)
  const mon = formatMonth(monthToDate.month, "short")
  const prevMon = formatMonth(monthToDate.previous_month, "short")

  const spent = monthToDate.expenses
  const comparison = formatChange(
    monthToDate.expenses_change_pct,
    monthToDate.previous_expenses,
  )
  const incomeComparison = formatChange(
    monthToDate.income_change_pct,
    monthToDate.previous_income,
  )
  const range = `1–${day} ${mon} · vs 1–${previousDay} ${prevMon}`
  const income = `Income ${formatAmount(monthToDate.income)}`
  const netText = `Net ${formatAmount(monthToDate.net)}`
  const days = `${day} of ${daysInMonth} days`

  return (
    <Card role="group" aria-labelledby={id} className="h-full">
      <CardHeader>
        <CardTitle
          id={id}
          className="text-sm font-medium text-muted-foreground"
        >
          {`${monthName} so far`}
        </CardTitle>
        <p className="text-xs text-muted-foreground">{range}</p>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <div className="space-y-1">
          <p className="text-xs text-muted-foreground">Spent</p>
          <p className="text-3xl font-semibold tabular-nums">
            {formatAmount(spent)}
          </p>
          {comparison && (
            <p className="text-sm text-muted-foreground">{comparison}</p>
          )}
        </div>
        <div className="space-y-1 text-sm tabular-nums">
          <p>
            {income}
            {incomeComparison && (
              <span className="text-muted-foreground">{` · ${incomeComparison}`}</span>
            )}
          </p>
          <p>{netText}</p>
        </div>
        <div className="mt-auto space-y-1">
          <div
            role="progressbar"
            aria-label="Days covered"
            aria-valuemin={0}
            aria-valuemax={daysInMonth}
            aria-valuenow={day}
            className="h-1.5 overflow-hidden rounded-full bg-muted"
          >
            <div
              className="h-full bg-primary"
              style={{
                width: `${daysInMonth ? (day / daysInMonth) * 100 : 0}%`,
              }}
            />
          </div>
          <p className="text-xs text-muted-foreground">{days}</p>
        </div>
      </CardContent>
    </Card>
  )
}
