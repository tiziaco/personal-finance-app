import type { TrendPointResponse } from "@app/api-client/types"
import { formatAmount } from "@/components/transactions/format"
import { formatMonth } from "./month"

export type TrendPoint = {
  month: string
  label: string
  income: number
  expenses: number
  incomeText: string
  expensesText: string
}

export function toTrendPoints(points: TrendPointResponse[]): TrendPoint[] {
  return points.map((p) => ({
    month: p.month,
    label: formatMonth(p.month, "short"),
    income: Number(p.income),
    expenses: Number(p.expenses),
    incomeText: formatAmount(p.income),
    expensesText: formatAmount(p.expenses),
  }))
}
