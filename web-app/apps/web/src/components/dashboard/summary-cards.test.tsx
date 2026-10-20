import { describe, it, expect } from "vitest"
import { render, screen } from "@testing-library/react"
import type { DashboardResponse } from "@app/api-client/types"
import { SummaryCards } from "./summary-cards"
import { formatMonth } from "./month"
import {
  formatAmount,
  formatSignedAmount,
} from "@/components/transactions/format"

const dashboard = (
  over: Partial<DashboardResponse> = {},
): DashboardResponse => ({
  reference_month: "2026-09",
  total_spent: "1395.00",
  recurring_spent: "915.00",
  recurring_count: 2,
  net_balance: "705.00",
  average_cashflow: "1235.00",
  cashflow_months: 3,
  spending_by_category: [],
  monthly_trend: [],
  reference_partial: false,
  month_to_date: null,
  ...over,
})

const card = (title: string) => screen.getByRole("group", { name: title })

describe("SummaryCards", () => {
  it("shows each figure with its subtitle", () => {
    render(<SummaryCards dashboard={dashboard()} />)
    expect(card("Total spent")).toHaveTextContent(formatAmount("1395.00"))
    expect(card("Total spent")).toHaveTextContent(formatMonth("2026-09"))
    expect(card("Recurring costs")).toHaveTextContent("2 recurring payments")
    expect(card("Net balance")).toHaveTextContent(formatSignedAmount("705.00"))
    expect(card("Average cashflow")).toHaveTextContent("average of 3 months")
  })

  it("uses the singular for one", () => {
    render(
      <SummaryCards
        dashboard={dashboard({ recurring_count: 1, cashflow_months: 1 })}
      />,
    )
    expect(card("Recurring costs")).toHaveTextContent("1 recurring payment")
    expect(card("Recurring costs")).not.toHaveTextContent("payments")
    expect(card("Average cashflow")).toHaveTextContent("average of 1 month")
  })

  it("signs a net and cashflow, red when negative", () => {
    render(
      <SummaryCards
        dashboard={dashboard({
          net_balance: "-40.00",
          average_cashflow: "-10.00",
        })}
      />,
    )
    expect(screen.getByText(formatSignedAmount("-40.00"))).toHaveClass(
      "text-negative",
    )
    expect(screen.getByText(formatSignedAmount("-10.00"))).toHaveClass(
      "text-negative",
    )
    expect(screen.getByText(formatAmount("1395.00"))).not.toHaveClass(
      "text-negative",
    )
  })

  it("greens a positive net and leaves the totals unsigned", () => {
    render(<SummaryCards dashboard={dashboard()} />)
    expect(screen.getByText(formatSignedAmount("705.00"))).toHaveClass(
      "text-positive",
    )
    expect(screen.getByText(formatAmount("1395.00")).textContent).not.toMatch(
      /^[+−]/,
    )
  })
})
