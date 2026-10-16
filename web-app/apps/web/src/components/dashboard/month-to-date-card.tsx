import { useId } from "react"
import type { MonthToDateResponse } from "@app/api-client/types"
import { Card, CardContent, CardHeader, CardTitle } from "@app/ui/card"
import { parseIsoDay } from "@app/core/lib/dates"
import { formatAmount } from "@/components/transactions/format"
import { formatMonth } from "./month"

const unsigned = (amount: string) => amount.trim().replace(/^-/, "")

/** "+12%" / "-5%" / "0%"; the server rounds to a float, the card to a whole percent. */
const formatPct = (pct: number) => {
  const rounded = Math.round(pct)
  return `${rounded > 0 ? "+" : ""}${rounded}%`
}

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
  const monthName = through
    ? new Intl.DateTimeFormat(undefined, { month: "long" }).format(through)
    : formatMonth(monthToDate.month)
  const mon = formatMonth(monthToDate.month, "short")
  const prevMon = formatMonth(monthToDate.previous_month, "short")

  const spent = unsigned(monthToDate.expenses)
  const previousSpent = unsigned(monthToDate.previous_expenses)
  const net = (Number(monthToDate.income) - Number(spent)).toFixed(2)
  const pct = monthToDate.expenses_change_pct
  const comparison =
    pct === null ? null : `${formatPct(pct)} vs ${formatAmount(previousSpent)}`
  const range = `1–${day} ${mon} · vs 1–${day} ${prevMon}`
  const income = `Income ${formatAmount(monthToDate.income)}`
  const netText = `Net ${formatAmount(net)}`
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
        <p className="text-sm tabular-nums">{`${income} · ${netText}`}</p>
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
