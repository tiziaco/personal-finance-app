import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import type { MonthToDateResponse } from "@app/api-client/types"
import { formatAmount } from "@/components/transactions/format"
import { MonthToDateCard } from "./month-to-date-card"

const mtd = (over: Partial<MonthToDateResponse> = {}): MonthToDateResponse => ({
  month: "2026-10",
  through: "2026-10-16",
  income: "2950.00",
  expenses: "1184.00",
  previous_month: "2026-09",
  previous_income: "2800.00",
  previous_expenses: "1057.00",
  income_change_pct: 5.4,
  expenses_change_pct: 12.02,
  ...over,
})

describe("MonthToDateCard", () => {
  it("shows spent, income and net with changes", () => {
    render(<MonthToDateCard monthToDate={mtd()} />)
    const card = screen.getByRole("group", { name: /so far/ })
    expect(card).toHaveTextContent(formatAmount("1184.00"))
    expect(card).toHaveTextContent(`+12% vs ${formatAmount("1057.00")}`)
    expect(card).toHaveTextContent(`Income ${formatAmount("2950.00")}`)
    expect(card).toHaveTextContent(`Net ${formatAmount("1766.00")}`)
    expect(card).toHaveTextContent("1–16")
    expect(card).toHaveTextContent("vs 1–16")
  })

  it("renders spent positive even when the server sends it negative", () => {
    render(<MonthToDateCard monthToDate={mtd({ expenses: "-1184.00" })} />)
    expect(screen.getByText(formatAmount("1184.00"))).toBeInTheDocument()
  })

  it("a null change pct shows no comparison", () => {
    render(<MonthToDateCard monthToDate={mtd({ expenses_change_pct: null })} />)
    const card = screen.getByRole("group", { name: /so far/ })
    expect(card).toHaveTextContent(formatAmount("1184.00"))
    expect(card).not.toHaveTextContent(`vs ${formatAmount("1057.00")}`)
    expect(card).not.toHaveTextContent("%")
  })

  it("shows days covered", () => {
    render(<MonthToDateCard monthToDate={mtd()} />)
    expect(screen.getByText("16 of 31 days")).toBeInTheDocument()
    expect(screen.getByRole("progressbar")).toHaveAttribute(
      "aria-valuenow",
      "16",
    )
  })
})
