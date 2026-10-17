import type { MonthToDateResponse } from "@app/api-client/types"
import { parseIsoDay } from "@app/core/lib/dates"
import { formatAmount } from "@/components/transactions/format"
import { Change } from "./change"
import { formatDayRange } from "./format"

/** "YYYY-MM" → the long month name, no year, in the user's locale. */
function monthName(month: string) {
  const [y, m] = month.split("-").map(Number)
  return new Intl.DateTimeFormat(undefined, { month: "long" }).format(
    new Date(y, m - 1, 1),
  )
}

/** This month so far, against the same days of the month before. Independent of the period. */
export function MonthToDateStrip({ data }: { data: MonthToDateResponse }) {
  // The day part of the server's date; no clock. Undefined only if the date is malformed.
  const day = parseIsoDay(data.through)?.getDate()
  const against =
    day === undefined ? null : formatDayRange(data.previous_month, day)
  const comparison = (pct: number | null, kind: "spend" | "income") => (
    <Change
      pct={against === null ? null : pct}
      kind={kind}
      up={`more than ${against}`}
      down={`less than ${against}`}
      empty="no comparison yet"
    />
  )
  return (
    <div className="flex flex-col gap-1 rounded-lg border bg-card p-4 text-sm">
      <p className="font-medium">
        {`${monthName(data.month)} so far `}
        {day === undefined ? null : (
          <span className="whitespace-nowrap">{`(${formatDayRange(data.month, day)})`}</span>
        )}
      </p>
      <p>
        Spent{" "}
        <span className="font-semibold tabular-nums">
          {formatAmount(data.expenses)}
        </span>{" "}
        {comparison(data.expenses_change_pct, "spend")}
      </p>
      <p>
        Income{" "}
        <span className="font-semibold tabular-nums">
          {formatAmount(data.income)}
        </span>{" "}
        {comparison(data.income_change_pct, "income")}
      </p>
    </div>
  )
}
