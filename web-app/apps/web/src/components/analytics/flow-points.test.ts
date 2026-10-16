import { describe, it, expect } from "vitest"
import { formatMonth } from "@/components/dashboard/month"
import { toFlowPoints } from "./flow-points"

describe("toFlowPoints", () => {
  it("maps numbers for geometry and keeps partial", () => {
    expect(
      toFlowPoints([
        {
          month: "2026-10",
          income: "3200.00",
          expenses: "1020.50",
          net: "2179.50",
          partial: true,
          expense_change_pct: null,
          expenses_rolling_avg_3m: null,
          savings_rate_pct: 68.1,
        },
      ]),
    ).toEqual([
      {
        month: "2026-10",
        label: formatMonth("2026-10", "short"),
        income: 3200,
        expenses: 1020.5,
        partial: true,
      },
    ])
  })
})
