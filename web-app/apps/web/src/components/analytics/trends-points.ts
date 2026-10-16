import type { MonthFlowResponse } from "@app/api-client/types"
import { formatMonth } from "@/components/dashboard/month"

/** One month as the trend charts draw it: numbers for geometry only; a null stays null so the line breaks. */
export type TrendsPoint = {
  month: string
  label: string
  expenses: number
  rollingAvg: number | null
  change: number | null
  savingsRate: number | null
  partial: boolean
}

export function toTrendsPoints(months: MonthFlowResponse[]): TrendsPoint[] {
  return months.map((m) => ({
    month: m.month,
    label: formatMonth(m.month, "short"),
    expenses: Number(m.expenses),
    rollingAvg:
      m.expenses_rolling_avg_3m === null
        ? null
        : Number(m.expenses_rolling_avg_3m),
    change: m.expense_change_pct,
    savingsRate: m.savings_rate_pct,
    partial: m.partial,
  }))
}
