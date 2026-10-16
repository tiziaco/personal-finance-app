import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useGetSpending } from "@app/api-client/endpoints/analytics"
import type { MonthFlowResponse, SpendingResponse } from "@app/api-client/types"
import { formatMonth } from "@/components/dashboard/month"
import { formatAmount } from "@/components/transactions/format"
import { FlowTab } from "./flow-tab"
import { formatDayRange, formatPct } from "./format"

vi.mock("@app/api-client/endpoints/analytics", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/analytics")>()),
  useGetSpending: vi.fn(),
}))
// jsdom can't lay out SVG.
vi.mock("./flow-chart", () => ({
  FlowChart: ({ points }: { points: unknown[] }) => (
    <div data-testid="flow-chart">{points.length} points</div>
  ),
}))

const refetch = vi.fn()
const flow = (month: string, partial = false): MonthFlowResponse => ({
  month,
  income: "3200.00",
  expenses: "2140.00",
  net: "1060.00",
  partial,
  expense_change_pct: null,
  expenses_rolling_avg_3m: null,
  savings_rate_pct: 33.13,
})

const DATA: SpendingResponse = {
  date_from: "2026-04-01",
  date_to: "2026-09-30",
  total_income: "19200.00",
  total_expenses: "12840.00",
  net: "6360.00",
  average_monthly_income: "3200.00",
  average_monthly_expenses: "2140.00",
  average_monthly_net: "1060.00",
  average_expense: "10.00",
  average_income: "10.00",
  burn_rate: "-1060.00",
  savings_rate_pct: 33.13,
  transaction_count: 120,
  months: ["04", "05", "06", "07", "08", "09"].map((m) => flow(`2026-${m}`)),
  latest_month: {
    month: "2026-09",
    income: "3330.00",
    expenses: "2397.00",
    income_vs_average_pct: 4.06,
    expenses_vs_average_pct: 12.02,
  },
  month_to_date: {
    month: "2026-10",
    through: "2026-10-16",
    previous_month: "2026-09",
    expenses: "1020.00",
    expenses_change_pct: -8.2,
    income: "3200.00",
    income_change_pct: 1.6,
    previous_expenses: "1111.00",
    previous_income: "3150.00",
  },
}

const spending = (state: object) =>
  vi.mocked(useGetSpending).mockReturnValue({
    data: undefined,
    isError: false,
    refetch,
    ...state,
  } as unknown as ReturnType<typeof useGetSpending>)

beforeEach(() => {
  vi.clearAllMocks()
  spending({ data: DATA })
})

const renderTab = (onMonthsChange = vi.fn()) =>
  render(<FlowTab months={6} onMonthsChange={onMonthsChange} />)

const card = (title: string | RegExp) =>
  screen.getByText(title).closest('[data-slot="card"]') as HTMLElement

// Intl.formatRange text has thin spaces the default normaliser collapses: match raw text.
const rawText = (text: string) =>
  screen.getByText((_, el) => el?.textContent === text && el.tagName === "P")

describe("FlowTab", () => {
  it("asks for the chosen period", async () => {
    const onMonthsChange = vi.fn()
    renderTab(onMonthsChange)
    expect(vi.mocked(useGetSpending).mock.calls[0][0]).toEqual({ months: 6 })
    await userEvent.click(screen.getByRole("button", { name: "12 months" }))
    expect(onMonthsChange).toHaveBeenCalledWith(12)
    expect(screen.getByTestId("flow-chart")).toHaveTextContent("6 points")
  })

  it("shows the month-to-date strip with its comparisons", () => {
    renderTab()
    const strip = rawText(`October so far (${formatDayRange("2026-10", 16)})`)
      .parentElement as HTMLElement
    expect(strip.textContent).toContain(formatAmount("1020.00"))
    expect(strip.textContent).toContain(
      `8.2% less than ${formatDayRange("2026-09", 16)}`,
    )
    expect(strip.textContent).toContain(
      `1.6% more than ${formatDayRange("2026-09", 16)}`,
    )
  })

  it("says no comparison yet for a null change", () => {
    spending({
      data: {
        ...DATA,
        month_to_date: { ...DATA.month_to_date!, expenses_change_pct: null },
      },
    })
    renderTab()
    expect(screen.getByText("no comparison yet")).toBeInTheDocument()
  })

  it("hides the strip when the period is the month in progress", () => {
    spending({
      data: {
        ...DATA,
        date_from: "2026-10-01",
        date_to: "2026-10-16",
        months: [flow("2026-10", true)],
        latest_month: null,
      },
    })
    renderTab()
    expect(screen.queryByText(/October so far/)).not.toBeInTheDocument()
    expect(screen.queryByText(/vs the period average/)).not.toBeInTheDocument()
  })

  it("shows totals, monthly averages and the savings rate", () => {
    renderTab()
    const cash = within(card("Cash flow"))
    expect(cash.getByText(formatAmount("19200.00"))).toBeInTheDocument()
    expect(cash.getByText(formatAmount("12840.00"))).toBeInTheDocument()
    expect(cash.getByText(`${formatAmount("1060.00")} / month`)).toBeTruthy()
    expect(cash.getByText("Kept 33.1% of income")).toBeInTheDocument()
  })

  it("shows a negative net and savings rate as negative", () => {
    spending({ data: { ...DATA, net: "-420.00", savings_rate_pct: -6.5 } })
    renderTab()
    const cash = within(card("Cash flow"))
    expect(cash.getByText(formatAmount("-420.00"))).toHaveClass(
      "text-destructive",
    )
    expect(cash.getByText(`Kept ${formatPct(-6.5)} of income`)).toHaveAttribute(
      "data-tone",
      "bad",
    )
  })

  it("shows a negative monthly net average as negative", () => {
    spending({ data: { ...DATA, average_monthly_net: "-70.00" } })
    renderTab()
    const el = within(card("Cash flow")).getByText(
      `${formatAmount("-70.00")} / month`,
    )
    expect(el).toHaveClass("text-destructive")
    expect(el).not.toHaveClass("text-muted-foreground")
  })

  it("shows a dash when there is no savings rate", () => {
    spending({ data: { ...DATA, savings_rate_pct: null } })
    renderTab()
    expect(within(card("Cash flow")).queryByText(/Kept/)).toBeNull()
    expect(within(card("Cash flow")).getByText("—")).toBeInTheDocument()
  })

  it("compares the latest month with the average", () => {
    renderTab()
    const latest = within(
      card(`${formatMonth("2026-09")} vs the period average`),
    )
    expect(latest.getByText(/12\.0% above average/)).toHaveAttribute(
      "data-tone",
      "bad",
    )
    expect(latest.getByText(/4\.1% above average/)).toHaveAttribute(
      "data-tone",
      "good",
    )
  })

  it("lists the months, marking a partial one", () => {
    spending({
      data: {
        ...DATA,
        months: [flow("2026-09"), flow("2026-10", true)],
      },
    })
    renderTab()
    const month = within(card("Month by month"))
    expect(month.getAllByText(/so far/)).toHaveLength(2) // table + card list
    expect(month.getAllByText("33.1%").length).toBeGreaterThan(0)
  })

  it("says 'so far' only for the month in progress, 'partial' for any other", () => {
    spending({
      data: {
        ...DATA,
        months: [flow("2026-04", true), flow("2026-10", true)],
      },
    })
    renderTab()
    const month = within(card("Month by month"))
    expect(month.getAllByText(/so far/)).toHaveLength(2) // table + card list
    expect(month.getAllByText(/partial/)).toHaveLength(2)
  })

  it("shows the empty state", () => {
    spending({
      data: {
        ...DATA,
        date_from: null,
        date_to: null,
        months: [],
        latest_month: null,
        month_to_date: null,
      },
    })
    const { container } = renderTab()
    expect(
      screen.getAllByText("No transactions in this period.").length,
    ).toBeGreaterThan(0)
    expect(screen.queryByText(/Kept/)).not.toBeInTheDocument()
    expect(container.textContent).not.toContain("€")
  })

  it("keeps data when a refetch fails", () => {
    spending({ data: DATA, isError: true })
    renderTab()
    expect(screen.getByText("Cash flow")).toBeInTheDocument()
    expect(screen.queryByText(/Couldn't load/)).not.toBeInTheDocument()
  })

  it("shows an error when nothing loaded", () => {
    spending({ data: undefined, isError: true })
    renderTab()
    expect(
      screen.getAllByText(/Couldn't load your income and expenses/).length,
    ).toBeGreaterThan(0)
  })
})
