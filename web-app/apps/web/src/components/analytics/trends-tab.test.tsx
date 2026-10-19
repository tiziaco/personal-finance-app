import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import {
  useGetCategoryBreakdown,
  useGetSpending,
} from "@app/api-client/endpoints/analytics"
import { useListTransactionCategories } from "@app/api-client/endpoints/transactions"
import type { MonthFlowResponse, SpendingResponse } from "@app/api-client/types"
import {
  formatAmount,
  formatSignedAmount,
} from "@/components/transactions/format"
import { TrendsTab } from "./trends-tab"
import { formatPct } from "./format"

vi.mock("@app/api-client/endpoints/analytics", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/analytics")>()),
  useGetSpending: vi.fn(),
  useGetCategoryBreakdown: vi.fn(),
}))
vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useListTransactionCategories: vi.fn(),
}))
// jsdom can't lay out SVG.
vi.mock("./trends-charts", () => ({
  SpendingTrendChart: ({ points }: { points: unknown[] }) => (
    <div data-testid="spending-chart">{points.length} points</div>
  ),
  MonthChangeChart: ({ points }: { points: unknown[] }) => (
    <div data-testid="change-chart">{points.length} points</div>
  ),
  SavingsRateChart: ({ points }: { points: unknown[] }) => (
    <div data-testid="savings-chart">{points.length} points</div>
  ),
}))

const refetch = vi.fn()
const flow = (month: string): MonthFlowResponse => ({
  month,
  income: "3200.00",
  expenses: "2140.00",
  net: "1060.00",
  partial: false,
  expense_change_pct: null,
  expenses_rolling_avg_3m: null,
  savings_rate_pct: 33.13,
})

const SPENDING: SpendingResponse = {
  date_from: "2026-06-01",
  date_to: "2026-09-30",
  total_income: "12800.00",
  total_expenses: "8560.00",
  net: "4240.00",
  average_monthly_income: "3200.00",
  average_monthly_expenses: "2140.00",
  average_monthly_net: "1060.00",
  average_expense: "10.00",
  average_income: "10.00",
  burn_rate: "-1060.00",
  savings_rate_pct: 33.13,
  transaction_count: 80,
  months: ["06", "07", "08", "09"].map((m, i) => ({
    ...flow(`2026-${m}`),
    expense_change_pct: i === 0 ? null : 4.2,
  })),
  latest_month: null,
  month_to_date: null,
}

const trend = (
  category: string,
  earlier: string,
  later: string,
  change_amount: string,
  change_pct: number | null,
) => ({
  category,
  earlier_monthly_average: earlier,
  later_monthly_average: later,
  change_amount,
  change_pct,
})

const CATEGORIES = {
  date_from: "2026-06-01",
  date_to: "2026-09-30",
  previous_date_from: null,
  previous_date_to: null,
  total_expenses: "8560.00",
  top_categories: [],
  by_frequency: [],
  top_growing: [
    trend("food_groceries", "320.00", "410.00", "90.00", 28.1),
    trend("travel", "0.00", "200.00", "200.00", null),
  ],
  top_declining: [trend("transport", "80.00", "0.00", "-80.00", -100)],
}

const spending = (state: object) =>
  vi.mocked(useGetSpending).mockReturnValue({
    data: undefined,
    isError: false,
    refetch,
    ...state,
  } as unknown as ReturnType<typeof useGetSpending>)
const categories = (state: object) =>
  vi.mocked(useGetCategoryBreakdown).mockReturnValue({
    data: undefined,
    isError: false,
    refetch,
    ...state,
  } as unknown as ReturnType<typeof useGetCategoryBreakdown>)

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useListTransactionCategories).mockReturnValue({
    data: [
      { value: "food_groceries", label: "Food & Groceries" },
      { value: "travel", label: "Travel" },
      { value: "transport", label: "Transport" },
    ],
  } as unknown as ReturnType<typeof useListTransactionCategories>)
  spending({ data: SPENDING })
  categories({ data: CATEGORIES })
})

const renderTab = (onMonthsChange = vi.fn()) =>
  render(<TrendsTab months={4} onMonthsChange={onMonthsChange} />)

const card = (title: string | RegExp) =>
  screen.getByText(title).closest('[data-slot="card"]') as HTMLElement

describe("TrendsTab", () => {
  it("asks for the chosen period", async () => {
    const onMonthsChange = vi.fn()
    renderTab(onMonthsChange)
    expect(vi.mocked(useGetSpending).mock.calls[0][0]).toEqual({ months: 4 })
    expect(vi.mocked(useGetCategoryBreakdown).mock.calls[0][0]).toEqual({
      months: 4,
      top_n: 1,
    })
    await userEvent.click(screen.getByRole("button", { name: "12 months" }))
    expect(onMonthsChange).toHaveBeenCalledWith(12)
    expect(screen.getByTestId("spending-chart")).toHaveTextContent("4 points")
    expect(screen.getByTestId("change-chart")).toBeInTheDocument()
    expect(screen.getByTestId("savings-chart")).toBeInTheDocument()
  })

  it("says a single month cannot be compared, with no change chart", () => {
    spending({ data: { ...SPENDING, months: [flow("2026-09")] } })
    renderTab()
    const part = within(card("Month-over-month change"))
    expect(
      part.getByText("Needs at least two months to compare."),
    ).toBeInTheDocument()
    expect(screen.queryByTestId("change-chart")).toBeNull()
  })

  it("draws the change chart when some month has a change", () => {
    spending({
      data: {
        ...SPENDING,
        months: [
          flow("2026-08"),
          { ...flow("2026-09"), expense_change_pct: 4.2 },
        ],
      },
    })
    renderTab()
    expect(screen.getByTestId("change-chart")).toBeInTheDocument()
    expect(
      screen.queryByText("Needs at least two months to compare."),
    ).toBeNull()
  })

  it("says no month has income when every savings rate is null", () => {
    spending({
      data: {
        ...SPENDING,
        months: SPENDING.months.map((m) => ({ ...m, savings_rate_pct: null })),
      },
    })
    renderTab()
    expect(
      within(card("Savings rate")).getByText("No month with income yet."),
    ).toBeInTheDocument()
    expect(screen.queryByTestId("savings-chart")).toBeNull()
  })

  it("shows movers with new and stopped", () => {
    renderTab()
    const growing = within(card("Growing"))
    expect(growing.getByText("Food & Groceries")).toBeInTheDocument()
    const pct = growing.getByText(formatPct(28.1))
    expect(pct).toHaveAttribute("data-tone", "bad")
    expect(pct).toHaveTextContent("▲")
    expect(growing.getByText("new")).toBeInTheDocument()
    expect(
      growing.getByText(
        `${formatAmount("320.00")} → ${formatAmount("410.00")} per month`,
      ),
    ).toBeInTheDocument()
    expect(growing.getByText(formatSignedAmount("90.00"))).toHaveClass(
      "text-negative",
    )

    const declining = within(card("Declining"))
    expect(declining.getByText(/stopped/)).toHaveAttribute("data-tone", "good")
    expect(declining.getByText(/stopped/)).toHaveTextContent("▼")
    expect(declining.getByText(formatSignedAmount("-80.00"))).toHaveClass(
      "text-positive",
    )
    expect(
      screen.getAllByText("Earlier half vs later half of the period, per month")
        .length,
    ).toBeGreaterThan(0)
  })

  it("colours a falling percent as good", () => {
    categories({
      data: {
        ...CATEGORIES,
        top_declining: [trend("transport", "80.00", "60.00", "-20.00", -25)],
      },
    })
    renderTab()
    expect(within(card("Declining")).getByText(formatPct(25))).toHaveAttribute(
      "data-tone",
      "good",
    )
  })

  it("shows the period savings rate", () => {
    renderTab()
    expect(
      within(card("Savings rate")).getByText("Kept 33.1% of income"),
    ).toHaveAttribute("data-tone", "good")
  })

  it("says Spent more than income for a negative rate", () => {
    spending({ data: { ...SPENDING, savings_rate_pct: -6.5 } })
    renderTab()
    expect(
      within(card("Savings rate")).getByText(
        `Spent ${formatPct(6.5)} more than income`,
      ),
    ).toHaveAttribute("data-tone", "bad")
  })

  it("says Kept 0.0% for a zero rate, neutral", () => {
    spending({ data: { ...SPENDING, savings_rate_pct: 0 } })
    renderTab()
    expect(
      within(card("Savings rate")).getByText("Kept 0.0% of income"),
    ).toHaveAttribute("data-tone", "neutral")
  })

  it.each([-0, -0.04])("says Kept 0.0%% for %s, neutral", (rate) => {
    spending({ data: { ...SPENDING, savings_rate_pct: rate } })
    renderTab()
    expect(
      within(card("Savings rate")).getByText("Kept 0.0% of income"),
    ).toHaveAttribute("data-tone", "neutral")
  })

  it("shows a dash when there is no savings rate", () => {
    spending({ data: { ...SPENDING, savings_rate_pct: null } })
    renderTab()
    expect(within(card("Savings rate")).queryByText(/Kept/)).toBeNull()
    expect(within(card("Savings rate")).getByText("—")).toBeInTheDocument()
  })

  it("explains empty mover lists without claiming nothing changed", () => {
    categories({
      data: { ...CATEGORIES, top_growing: [], top_declining: [] },
    })
    renderTab()
    expect(
      screen.getByText(
        "No category grew or declined between the two halves of the period.",
      ),
    ).toBeInTheDocument()
    expect(
      screen.getAllByText("Needs at least two whole months."),
    ).toHaveLength(1)
    expect(screen.queryByText("Growing")).toBeNull()
    expect(screen.queryByText("Declining")).toBeNull()
  })

  it("names the empty list when only one is empty", () => {
    categories({ data: { ...CATEGORIES, top_growing: [] } })
    renderTab()
    expect(
      screen.getByText(
        "No category grew between the two halves of the period.",
      ),
    ).toBeInTheDocument()
    expect(
      screen.queryByText("Needs at least two whole months."),
    ).not.toBeInTheDocument()
  })

  it("says there are no transactions when the period is empty", () => {
    categories({
      data: {
        ...CATEGORIES,
        date_from: null,
        date_to: null,
        top_growing: [],
        top_declining: [],
      },
    })
    renderTab()
    expect(screen.getAllByText("No transactions in this period.")).toHaveLength(
      1,
    )
    expect(
      screen.queryByText("Needs at least two whole months."),
    ).not.toBeInTheDocument()
  })

  it("shows the empty state", () => {
    spending({
      data: { ...SPENDING, date_from: null, date_to: null, months: [] },
    })
    categories({
      data: { ...CATEGORIES, date_from: null, date_to: null },
    })
    const { container } = renderTab()
    expect(screen.getAllByText("No transactions in this period.")).toHaveLength(
      2,
    )
    expect(screen.queryByText(/Kept/)).not.toBeInTheDocument()
    expect(container.textContent).not.toContain("€")
  })

  it("keeps data when a refetch fails", () => {
    spending({ data: SPENDING, isError: true })
    categories({ data: CATEGORIES, isError: true })
    renderTab()
    expect(screen.getByText("Savings rate")).toBeInTheDocument()
    expect(screen.queryByText(/Couldn't load/)).not.toBeInTheDocument()
  })

  it("shows an error when nothing loaded", () => {
    spending({ data: undefined, isError: true })
    categories({ data: undefined, isError: true })
    renderTab()
    expect(
      screen.getAllByText(/Couldn't load your spending trend/),
    ).toHaveLength(1)
    expect(
      screen.getAllByText(/Couldn't load your category movers/),
    ).toHaveLength(1)
  })
})
