import { describe, it, expect, vi } from "vitest"
import { render, screen, within } from "@testing-library/react"
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

  it("turns 'Recurring only' on", async () => {
    const setFilters = vi.fn()
    render(
      <TransactionsFilterPanel
        filters={EMPTY_TRANSACTIONS_FILTERS}
        setFilters={setFilters}
        categories={[]}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    const toggle = await screen.findByRole("switch", { name: "Recurring only" })
    expect(toggle).not.toBeChecked()
    await userEvent.click(toggle)
    const update = setFilters.mock.calls[0][0] as (
      f: TransactionsFilters,
    ) => TransactionsFilters
    expect(update(EMPTY_TRANSACTIONS_FILTERS).recurring).toBe(true)
  })

  it("turns 'Recurring only' off to no filter", async () => {
    const setFilters = vi.fn()
    const on = { ...EMPTY_TRANSACTIONS_FILTERS, recurring: true }
    render(
      <TransactionsFilterPanel
        filters={on}
        setFilters={setFilters}
        categories={[]}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    const toggle = await screen.findByRole("switch", { name: "Recurring only" })
    expect(toggle).toBeChecked()
    await userEvent.click(toggle)
    const update = setFilters.mock.calls[0][0] as (
      f: TransactionsFilters,
    ) => TransactionsFilters
    expect(update(on).recurring).toBeNull()
  })

  it("shows the switch off for an old recurring=false link, still counted", async () => {
    render(
      <TransactionsFilterPanel
        filters={{ ...EMPTY_TRANSACTIONS_FILTERS, recurring: false }}
        setFilters={vi.fn()}
        categories={[]}
      />,
    )
    expect(screen.getByRole("button", { name: /Filters/ })).toHaveTextContent(
      "1",
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    expect(
      await screen.findByRole("switch", { name: "Recurring only" }),
    ).not.toBeChecked()
  })

  it("groups min and max under Amount range", async () => {
    render(
      <TransactionsFilterPanel
        filters={EMPTY_TRANSACTIONS_FILTERS}
        setFilters={vi.fn()}
        categories={[]}
      />,
    )
    await userEvent.click(screen.getByRole("button", { name: /Filters/ }))
    const group = await screen.findByRole("group", { name: "Amount range" })
    expect(within(group).getByLabelText("Min")).toBeInTheDocument()
    expect(within(group).getByLabelText("Max")).toBeInTheDocument()
  })
})
