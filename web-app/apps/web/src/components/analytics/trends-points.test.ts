import { describe, it, expect } from "vitest"
import type { MonthFlowResponse } from "@app/api-client/types"
import { formatMonth } from "@/components/dashboard/month"
import { toTrendsPoints } from "./trends-points"

const month = (over: Partial<MonthFlowResponse>): MonthFlowResponse => ({
  month: "2026-09",
  income: "3200.00",
  expenses: "2100.00",
  net: "1100.00",
  partial: false,
  expense_change_pct: null,
  expenses_rolling_avg_3m: null,
  savings_rate_pct: null,
  ...over,
})

describe("toTrendsPoints", () => {
  it("keeps nulls as gaps", () => {
    expect(toTrendsPoints([month({})])).toEqual([
      {
        month: "2026-09",
        label: formatMonth("2026-09", "short"),
        expenses: 2100,
        rollingAvg: null,
        change: null,
        savingsRate: null,
        partial: false,
      },
    ])
  })

  it("parses the rolling average", () => {
    const [point] = toTrendsPoints([
      month({ expenses_rolling_avg_3m: "2050.33", expense_change_pct: 4.5 }),
    ])
    expect(point.rollingAvg).toBe(2050.33)
    expect(point.change).toBe(4.5)
  })
})
