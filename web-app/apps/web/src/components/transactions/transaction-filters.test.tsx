import { describe, it, expect, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { EMPTY_DATE_FILTER } from "@app/data-table/url-state/date-filter"
import {
  TransactionsFilterChips,
  TransactionsFilterPanel,
} from "./transaction-filters"
import {
  EMPTY_TRANSACTIONS_FILTERS,
  type TransactionsFilters,
} from "./transactions-table-params"

const labels: Record<string, string> = { salary: "Salary", atm: "ATM" }
const label = (s: string) => labels[s] ?? s

const filters: TransactionsFilters = {
  categories: ["salary", "atm"],
  amountMin: "-50",
  amountMax: "200",
  recurring: true,
  date: { ...EMPTY_DATE_FILTER, mode: "gte", date1: "2026-01-01" },
}

describe("TransactionsFilterChips", () => {
  it("renders one chip per active filter", () => {
    render(
      <TransactionsFilterChips
        filters={filters}
        setFilters={vi.fn()}
        label={label}
      />,
    )
    expect(screen.getByText("Category: Salary")).toBeInTheDocument()
    expect(screen.getByText("Category: ATM")).toBeInTheDocument()
    expect(screen.getByText("Amount ≥ -50")).toBeInTheDocument()
    expect(screen.getByText("Amount ≤ 200")).toBeInTheDocument()
    expect(screen.getByText("Recurring")).toBeInTheDocument()
    expect(screen.getByText(/Date/)).toBeInTheDocument()
  })

  it("removing a category chip keeps the other", async () => {
    const setFilters = vi.fn()
    render(
      <TransactionsFilterChips
        filters={filters}
        setFilters={setFilters}
        label={label}
      />,
    )
    const chip = screen
      .getByText("Category: Salary")
      .closest("button, div") as HTMLElement
    const remove =
      chip.tagName === "BUTTON" ? chip : chip.querySelector("button")!
    await userEvent.click(remove)
    const update = setFilters.mock.calls[0][0] as (
      f: TransactionsFilters,
    ) => TransactionsFilters
    expect(update(filters).categories).toEqual(["atm"])
  })
})

describe("TransactionsFilterPanel", () => {
  it("shows the active count", () => {
    render(
      <TransactionsFilterPanel
        filters={filters}
        setFilters={vi.fn()}
        categories={[]}
      />,
    )
    expect(screen.getByText("5")).toBeInTheDocument()
  })
  it("shows no badge when nothing is active", () => {
    render(
      <TransactionsFilterPanel
        filters={EMPTY_TRANSACTIONS_FILTERS}
        setFilters={vi.fn()}
        categories={[]}
      />,
    )
    expect(screen.queryByText("0")).toBeNull()
  })
})
