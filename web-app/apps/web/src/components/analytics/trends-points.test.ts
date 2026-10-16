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
    expect(toTrendsPoints([month({})], "2026-10")).toEqual([
      {
        month: "2026-09",
        label: formatMonth("2026-09", "short"),
        expenses: 2100,
        rollingAvg: null,
        change: null,
        savingsRate: null,
        partial: false,
        partialLabel: null,
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

  it("says so far only for the current month", () => {
    const points = toTrendsPoints(
      [
        month({ month: "2026-08", partial: true }),
        month({ month: "2026-10", partial: true }),
      ],
      "2026-10",
    )
    expect(points.map((p) => p.partialLabel)).toEqual(["partial", "so far"])
  })
})
