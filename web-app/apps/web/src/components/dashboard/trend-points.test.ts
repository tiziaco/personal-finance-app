import { describe, it, expect } from "vitest"
import { toTrendPoints } from "./trend-points"
import { formatMonth } from "./month"
import { formatAmount } from "@/components/transactions/format"

describe("toTrendPoints", () => {
  it("turns decimal strings into plottable numbers and keeps the exact text for the tooltip", () => {
    expect(
      toTrendPoints([
        { month: "2026-09", income: "2100.00", expenses: "1395.50" },
      ]),
    ).toEqual([
      {
        month: "2026-09",
        label: formatMonth("2026-09", "short"),
        income: 2100,
        expenses: 1395.5,
        incomeText: formatAmount("2100.00"),
        expensesText: formatAmount("1395.50"),
      },
    ])
  })
})
