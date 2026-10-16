import { describe, it, expect } from "vitest"
import { formatMonth } from "@/components/dashboard/month"
import { toFlowPoints } from "./flow-points"

describe("toFlowPoints", () => {
  it("maps numbers for geometry and keeps partial", () => {
    expect(
      toFlowPoints(
        [
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
        ],
        "2026-10",
      ),
    ).toEqual([
      {
        month: "2026-10",
        label: formatMonth("2026-10", "short"),
        income: 3200,
        expenses: 1020.5,
        partial: true,
        partialLabel: "so far",
      },
    ])
  })

  it("labels a partial month other than the current one 'partial'", () => {
    const base = {
      income: "1.00",
      expenses: "1.00",
      net: "0.00",
      expense_change_pct: null,
      expenses_rolling_avg_3m: null,
      savings_rate_pct: null,
    }
    const points = toFlowPoints(
      [
        { ...base, month: "2026-08", partial: true },
        { ...base, month: "2026-09", partial: false },
      ],
      "2026-10",
    )
    expect(points.map((p) => p.partialLabel)).toEqual(["partial", null])
  })
})
