import type { MonthFlowResponse, SpendingResponse } from "@app/api-client/types"
import { formatMonth } from "@/components/dashboard/month"

/** One month as the chart draws it: numbers for geometry only, never shown as text. */
export type FlowPoint = {
  month: string
  label: string
  income: number
  expenses: number
  partial: boolean
}

export function toFlowPoints(months: MonthFlowResponse[]): FlowPoint[] {
  return months.map((m) => ({
    month: m.month,
    label: formatMonth(m.month, "short"),
    income: Number(m.income),
    expenses: Number(m.expenses),
    partial: m.partial,
  }))
}

/**
 * Whether the month-to-date strip adds anything: not when there is none, and
 * not when the period already holds that month (the server's fallback when no
 * finished month has data), which would repeat the chart.
 */
export function showMonthToDate(data: SpendingResponse): boolean {
  const mtd = data.month_to_date
  return mtd !== null && !data.months.some((m) => m.month === mtd.month)
}
