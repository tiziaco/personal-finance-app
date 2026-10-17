import { describe, it, expect } from "vitest"
import type {
  MonthFlowResponse,
  MonthToDateResponse,
  SpendingResponse,
} from "@app/api-client/types"
import { formatMonth } from "@/components/dashboard/month"
import { monthToDate, toMonthPoints } from "./month-points"

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

describe("toMonthPoints", () => {
  it("maps numbers for geometry and keeps partial", () => {
    expect(
      toMonthPoints(
        [
          month({
            month: "2026-10",
            income: "3200.00",
            expenses: "1020.50",
            net: "2179.50",
            partial: true,
            savings_rate_pct: 68.1,
          }),
        ],
        "2026-10",
      ),
    ).toEqual([
      {
        month: "2026-10",
        label: formatMonth("2026-10", "short"),
        income: 3200,
        expenses: 1020.5,
        rollingAvg: null,
        change: null,
        savingsRate: 68.1,
        partial: true,
        partialLabel: "so far",
      },
    ])
  })

  it("keeps nulls as gaps", () => {
    expect(toMonthPoints([month({})], "2026-10")).toEqual([
      {
        month: "2026-09",
        label: formatMonth("2026-09", "short"),
        income: 3200,
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
    const [point] = toMonthPoints([
      month({ expenses_rolling_avg_3m: "2050.33", expense_change_pct: 4.5 }),
    ])
    expect(point.rollingAvg).toBe(2050.33)
    expect(point.change).toBe(4.5)
  })

  it("labels a partial month other than the current one 'partial'", () => {
    const points = toMonthPoints(
      [
        month({ month: "2026-08", partial: true }),
        month({ month: "2026-09", partial: false }),
      ],
      "2026-10",
    )
    expect(points.map((p) => p.partialLabel)).toEqual(["partial", null])
  })

  it("says so far only for the current month", () => {
    const points = toMonthPoints(
      [
        month({ month: "2026-08", partial: true }),
        month({ month: "2026-10", partial: true }),
      ],
      "2026-10",
    )
    expect(points.map((p) => p.partialLabel)).toEqual(["partial", "so far"])
  })
})

describe("monthToDate", () => {
  const mtd = { month: "2026-10" } as MonthToDateResponse
  const data = (
    months: MonthFlowResponse[],
    month_to_date: MonthToDateResponse | null,
  ) => ({ months, month_to_date }) as SpendingResponse

  it("returns the strip when the period does not hold that month", () => {
    expect(monthToDate(data([month({})], mtd))).toBe(mtd)
  })

  it("is null when there is none", () => {
    expect(monthToDate(data([month({})], null))).toBeNull()
  })

  it("is null when the period already holds that month", () => {
    expect(
      monthToDate(data([month({ month: "2026-10", partial: true })], mtd)),
    ).toBeNull()
  })
})
