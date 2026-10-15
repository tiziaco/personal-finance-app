import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { useGetDashboard } from "@app/api-client/endpoints/analytics"
import {
  useListTransactions,
  useListTransactionCategories,
} from "@app/api-client/endpoints/transactions"
import { useAppAuth } from "@app/auth"
import { HomeDashboard } from "./home-dashboard"

vi.mock("@app/api-client/endpoints/analytics", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/analytics")>()),
  useGetDashboard: vi.fn(),
}))
vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useListTransactions: vi.fn(),
  useListTransactionCategories: vi.fn(),
}))
vi.mock("@app/auth", () => ({ useAppAuth: vi.fn() }))
// jsdom cannot lay out SVG; the charts' mapping is tested on its own.
vi.mock("./category-chart", () => ({
  CategoryChart: () => <div>category chart</div>,
}))
vi.mock("./trend-chart", () => ({ TrendChart: () => <div>trend chart</div> }))

const dashboardRefetch = vi.fn()
const recentRefetch = vi.fn()

const DATA = {
  reference_month: "2026-09",
  total_spent: "1395.00",
  recurring_spent: "915.00",
  recurring_count: 2,
  net_balance: "705.00",
  average_cashflow: "1235.00",
  cashflow_months: 3,
  spending_by_category: [],
  monthly_trend: [],
}

const dashboard = (state: object) =>
  vi.mocked(useGetDashboard).mockReturnValue({
    isPending: false,
    isError: false,
    data: undefined,
    refetch: dashboardRefetch,
    ...state,
  } as unknown as ReturnType<typeof useGetDashboard>)

const recent = (state: object) =>
  vi.mocked(useListTransactions).mockReturnValue({
    isPending: false,
    isError: false,
    data: undefined,
    refetch: recentRefetch,
    ...state,
  } as unknown as ReturnType<typeof useListTransactions>)

const TXN = {
  id: "1",
  date: "2026-09-05",
  merchant: "REWE",
  amount: "-200.00",
  category: "food_groceries",
  confidence: 1,
  description: null,
  original_category: null,
  is_recurring: false,
  created_at: "2026-09-05T10:00:00Z",
  updated_at: "2026-09-05T10:00:00Z",
}

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useAppAuth).mockReturnValue({
    user: { name: "Ada", email: null, imageUrl: null },
    isLoaded: true,
  } as unknown as ReturnType<typeof useAppAuth>)
  vi.mocked(useListTransactionCategories).mockReturnValue({
    data: [{ value: "food_groceries", label: "Food & Groceries" }],
  } as unknown as ReturnType<typeof useListTransactionCategories>)
  recent({ data: { items: [TXN], total: 1, offset: 0, limit: 10 } })
})

describe("HomeDashboard", () => {
  it("asks for the dashboard silently, with a two-minute stale time, and ten recent rows", () => {
    dashboard({ data: DATA })
    render(<HomeDashboard />)
    const options = vi.mocked(useGetDashboard).mock.calls[0][0]
    expect(options?.query?.staleTime).toBe(120_000)
    expect(options?.query?.meta?.silentError).toBe(true)
    expect(vi.mocked(useListTransactions).mock.calls[0][0]).toEqual({
      limit: 10,
    })
  })

  it("draws the cards, the charts and the recent transactions", () => {
    dashboard({ data: DATA })
    render(<HomeDashboard />)
    expect(
      screen.getByRole("group", { name: "Total Spent" }),
    ).toBeInTheDocument()
    expect(screen.getByText("category chart")).toBeInTheDocument()
    expect(screen.getByText("trend chart")).toBeInTheDocument()
    expect(screen.getAllByText("REWE").length).toBeGreaterThan(0)
    expect(screen.getByRole("link", { name: "View all" })).toHaveAttribute(
      "href",
      "/transactions",
    )
  })

  it("shows the empty state, linking to /transactions, for a user with no data", () => {
    dashboard({ data: { ...DATA, reference_month: null } })
    render(<HomeDashboard />)
    expect(screen.getByText("No transactions yet")).toBeInTheDocument()
    expect(
      screen.getByRole("link", { name: "Go to transactions" }),
    ).toHaveAttribute("href", "/transactions")
    expect(
      screen.queryByRole("group", { name: "Total Spent" }),
    ).not.toBeInTheDocument()
    expect(screen.queryByText("Recent transactions")).not.toBeInTheDocument()
  })

  it("a failed dashboard offers a retry and the recent list still renders", async () => {
    dashboard({ isError: true })
    render(<HomeDashboard />)
    expect(screen.getByText("Couldn't load your overview.")).toBeInTheDocument()
    expect(screen.getAllByText("REWE").length).toBeGreaterThan(0)
    await userEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(dashboardRefetch).toHaveBeenCalled()
  })

  it("a failed recent list offers its own retry and the cards still render", async () => {
    dashboard({ data: DATA })
    recent({ isError: true })
    render(<HomeDashboard />)
    expect(
      screen.getByRole("group", { name: "Total Spent" }),
    ).toBeInTheDocument()
    expect(
      screen.getByText("Couldn't load recent transactions."),
    ).toBeInTheDocument()
    await userEvent.click(screen.getByRole("button", { name: "Retry" }))
    expect(recentRefetch).toHaveBeenCalled()
  })

  it("a failed background refetch keeps the cards and offers no retry", () => {
    dashboard({ isError: true, data: DATA })
    recent({
      isError: true,
      data: { items: [TXN], total: 1, offset: 0, limit: 10 },
    })
    render(<HomeDashboard />)
    expect(
      screen.getByRole("group", { name: "Total Spent" }),
    ).toBeInTheDocument()
    expect(screen.queryByText(/Couldn't load/)).not.toBeInTheDocument()
    expect(
      screen.queryByRole("button", { name: "Retry" }),
    ).not.toBeInTheDocument()
    expect(screen.getAllByText("REWE").length).toBeGreaterThan(0)
  })

  it("shows skeletons, never nothing, while loading", () => {
    dashboard({ isPending: true })
    recent({ isPending: true })
    const { container } = render(<HomeDashboard />)
    expect(
      container.querySelectorAll('[data-slot="skeleton"]').length,
    ).toBeGreaterThan(0)
  })
})
