import type {
  MonthFlowResponse,
  MonthToDateResponse,
  SpendingResponse,
} from "@app/api-client/types"
import { formatMonth } from "@/components/dashboard/month"
import { partialLabel, type PartialLabel } from "./format"

/** One month as the charts draw it: numbers for geometry only, never shown as text; a null stays null so a line breaks. */
export type MonthPoint = {
  month: string
  label: string
  partial: boolean
  partialLabel: PartialLabel | null
  income: number
  expenses: number
  rollingAvg: number | null
  change: number | null
  savingsRate: number | null
}

export function toMonthPoints(
  months: MonthFlowResponse[],
  currentMonth?: string | null,
): MonthPoint[] {
  return months.map((m) => ({
    month: m.month,
    label: formatMonth(m.month, "short"),
    partial: m.partial,
    partialLabel: partialLabel(m.partial, m.month, currentMonth),
    income: Number(m.income),
    expenses: Number(m.expenses),
    rollingAvg:
      m.expenses_rolling_avg_3m === null
        ? null
        : Number(m.expenses_rolling_avg_3m),
    change: m.expense_change_pct,
    savingsRate: m.savings_rate_pct,
  }))
}

/**
 * The month-to-date strip to show, or null when it adds nothing: there is
 * none, or the period already holds that month (the server's fallback when no
 * finished month has data), which would repeat the chart.
 */
export function monthToDate(
  data: SpendingResponse,
): MonthToDateResponse | null {
  const mtd = data.month_to_date
  if (mtd === null || data.months.some((m) => m.month === mtd.month)) {
    return null
  }
  return mtd
}
