import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import type { MonthToDateResponse } from "@app/api-client/types"
import {
  formatAmount,
  formatSignedAmount,
} from "@/components/transactions/format"
import { MonthToDateCard } from "./month-to-date-card"

const mtd = (over: Partial<MonthToDateResponse> = {}): MonthToDateResponse => ({
  month: "2026-10",
  through: "2026-10-16",
  income: "2950.00",
  expenses: "1184.00",
  previous_month: "2026-09",
  previous_through: "2026-09-16",
  net: "1766.00",
  previous_income: "2800.00",
  previous_expenses: "1057.00",
  income_change_pct: 5.4,
  expenses_change_pct: 12.02,
  ...over,
})

/** A footer stat, income or net: its term and the definitions under it. */
const stat = (term: string) =>
  screen.getByText(term, { selector: "dt" }).parentElement!

describe("MonthToDateCard", () => {
  it("shows spent, income and net with changes", () => {
    render(<MonthToDateCard monthToDate={mtd()} />)
    const card = screen.getByRole("group", { name: /so far/ })
    expect(card).toHaveTextContent(formatAmount("1184.00"))
    expect(card).toHaveTextContent(`+12% vs ${formatAmount("1057.00")}`)
    expect(stat("Income")).toHaveTextContent(formatAmount("2950.00"))
    expect(stat("Net")).toHaveTextContent(formatSignedAmount("1766.00"))
    expect(card).toHaveTextContent("1–16")
    expect(card).toHaveTextContent("vs 1–16")
  })

  it("a null change pct shows no comparison", () => {
    render(<MonthToDateCard monthToDate={mtd({ expenses_change_pct: null })} />)
    const card = screen.getByRole("group", { name: /so far/ })
    expect(card).toHaveTextContent(formatAmount("1184.00"))
    expect(card).not.toHaveTextContent(`vs ${formatAmount("1057.00")}`)
    expect(card).not.toHaveTextContent("12%")
  })

  it("shows income's change with income", () => {
    render(<MonthToDateCard monthToDate={mtd()} />)
    expect(stat("Income")).toHaveTextContent(
      `+5% vs ${formatAmount("2800.00")}`,
    )
  })

  it("a null income change shows no income comparison", () => {
    render(<MonthToDateCard monthToDate={mtd({ income_change_pct: null })} />)
    const card = screen.getByRole("group", { name: /so far/ })
    expect(stat("Income")).toHaveTextContent(formatAmount("2950.00"))
    expect(card).not.toHaveTextContent(`vs ${formatAmount("2800.00")}`)
    expect(card).toHaveTextContent(`+12% vs ${formatAmount("1057.00")}`)
  })

  it("writes a fall with a true minus sign", () => {
    render(
      <MonthToDateCard
        monthToDate={mtd({
          expenses_change_pct: -5.4,
          income_change_pct: -12.6,
        })}
      />,
    )
    const card = screen.getByRole("group", { name: /so far/ })
    expect(card).toHaveTextContent(`\u22125% vs ${formatAmount("1057.00")}`)
    expect(card).toHaveTextContent(`\u221213% vs ${formatAmount("2800.00")}`)
    expect(card).not.toHaveTextContent("-5%")
  })

  it("names the previous range from the server's previous_through", () => {
    render(
      <MonthToDateCard
        monthToDate={mtd({
          through: "2026-10-31",
          previous_through: "2026-09-30",
        })}
      />,
    )
    const range = screen.getByText(/· vs 1–/)
    expect(range.textContent).toMatch(/^1–31 .+ · vs 1–30 /)
  })

  it("renders the server's net, not income minus expenses", () => {
    render(<MonthToDateCard monthToDate={mtd({ net: "-123.45" })} />)
    expect(stat("Net")).toHaveTextContent(formatSignedAmount("-123.45"))
  })
})
