import { render, screen } from "@testing-library/react"
import { describe, expect, it } from "vitest"
import type { MonthToDateResponse } from "@app/api-client/types"
import { formatAmount } from "@/components/transactions/format"
import { MonthToDateStrip } from "./month-to-date-strip"

const DATA: MonthToDateResponse = {
  month: "2026-10",
  through: "2026-10-16",
  previous_month: "2026-09",
  expenses: "1020.00",
  expenses_change_pct: -8.2,
  income: "3200.00",
  income_change_pct: 1.6,
  previous_expenses: "1111.00",
  previous_income: "3150.00",
}

describe("MonthToDateStrip", () => {
  it("without a parseable date shows no day range and no comparison", () => {
    const { container } = render(
      <MonthToDateStrip data={{ ...DATA, through: "2026-02-30" }} />,
    )
    const month = new Intl.DateTimeFormat(undefined, { month: "long" }).format(
      new Date(2026, 9, 1),
    )
    expect(screen.getByText(`${month} so far`, { exact: false })).toBeTruthy()
    expect(container.textContent).not.toContain("(")
    expect(screen.getAllByText("no comparison yet")).toHaveLength(2)
    expect(container.textContent).toContain(formatAmount("1020.00"))
    expect(container.textContent).toContain(formatAmount("3200.00"))
  })
})
