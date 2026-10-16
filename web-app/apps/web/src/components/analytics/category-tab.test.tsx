import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import {
  useGetCategoryBreakdown,
  useGetMerchantBreakdown,
} from "@app/api-client/endpoints/analytics"
import { useListTransactionCategories } from "@app/api-client/endpoints/transactions"
import { formatAmount } from "@/components/transactions/format"
import { CategoryTab } from "./category-tab"
import { formatPeriod } from "./format"

vi.mock("@app/api-client/endpoints/analytics", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/analytics")>()),
  useGetCategoryBreakdown: vi.fn(),
  useGetMerchantBreakdown: vi.fn(),
}))
vi.mock("@app/api-client/endpoints/transactions", async (orig) => ({
  ...(await orig<typeof import("@app/api-client/endpoints/transactions")>()),
  useListTransactionCategories: vi.fn(),
}))

const refetch = vi.fn()
const spend = (category: string, total: string, share_pct: number) => ({
  category,
  total,
  share_pct,
  count: 4,
  average: "10.00",
  change_pct: null as number | null,
  previous_total: null as string | null,
})

const DATA = {
  date_from: "2026-07-01",
  date_to: "2026-09-30",
  previous_date_from: "2026-04-01",
  previous_date_to: "2026-06-30",
  total_expenses: "6420.00",
  top_categories: [
    {
      ...spend("food_groceries", "1130.40", 17.6),
      previous_total: "1043.80",
      change_pct: 8.3,
    },
    { ...spend("travel", "240.00", 3.7), previous_total: "0.00" },
    spend("rent", "2700.00", 42.1),
  ],
  by_frequency: [spend("food_groceries", "1130.40", 17.6)],
  top_growing: [],
  top_declining: [],
}
const EMPTY = {
  ...DATA,
  date_from: null,
  date_to: null,
  previous_date_from: null,
  previous_date_to: null,
  total_expenses: "0.00",
  top_categories: [],
  by_frequency: [],
}
const MERCHANTS = {
  top_by_spend: [
    {
      merchant: "REWE",
      count: 6,
      total: "300.00",
      average: "50.00",
      share_pct: 4.7,
      first_date: "2026-07-02",
      last_date: "2026-09-20",
    },
  ],
}

const categories = (state: object) =>
  vi.mocked(useGetCategoryBreakdown).mockReturnValue({
    data: undefined,
    isError: false,
    refetch,
    ...state,
  } as unknown as ReturnType<typeof useGetCategoryBreakdown>)
const merchants = (state: object) =>
  vi.mocked(useGetMerchantBreakdown).mockReturnValue({
    data: undefined,
    isError: false,
    refetch,
    ...state,
  } as unknown as ReturnType<typeof useGetMerchantBreakdown>)

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(useListTransactionCategories).mockReturnValue({
    data: [
      { value: "food_groceries", label: "Food & Groceries" },
      { value: "travel", label: "Travel" },
      { value: "rent", label: "Rent" },
    ],
  } as unknown as ReturnType<typeof useListTransactionCategories>)
  categories({ data: DATA })
  merchants({ data: MERCHANTS })
})

const renderTab = (onMonthsChange = vi.fn()) =>
  render(<CategoryTab months={3} onMonthsChange={onMonthsChange} />)

const row = (name: string) =>
  within(screen.getByRole("list", { name: "Spending by category" }))
    .getByText(name)
    .closest("li") as HTMLElement

describe("CategoryTab", () => {
  it("labels the period and the comparison", () => {
    renderTab()
    // formatRange puts thin/no-break spaces in; match the raw text, not the normalised one.
    const hasText = (text: string) =>
      screen.getByText(
        (_, el) => el?.textContent === text && el.tagName === "P",
      )
    expect(
      hasText(formatPeriod("2026-07-01", "2026-09-30")!),
    ).toBeInTheDocument()
    expect(
      hasText(`compared with ${formatPeriod("2026-04-01", "2026-06-30")}`),
    ).toBeInTheDocument()
    expect(screen.getByText(formatAmount("6420.00"))).toBeInTheDocument()
  })

  it("shows change, new and no comparison", () => {
    renderTab()
    expect(
      within(row("Food & Groceries")).getByText(/8\.3%\s*more/),
    ).toBeTruthy()
    expect(within(row("Travel")).getByText("new")).toBeInTheDocument()
    expect(within(row("Rent")).getByText("—")).toBeInTheDocument()
  })

  it("does not pluralise a single purchase", () => {
    categories({
      data: { ...DATA, by_frequency: [{ ...DATA.by_frequency[0], count: 1 }] },
    })
    merchants({
      data: {
        top_by_spend: [{ ...MERCHANTS.top_by_spend[0], count: 1 }],
      },
    })
    renderTab()
    expect(screen.queryByText(/\b1 purchases/)).toBeNull()
    expect(screen.getAllByText(/\b1 purchase ·/)).toHaveLength(2)
  })

  it("asks for the chosen period", async () => {
    const onMonthsChange = vi.fn()
    renderTab(onMonthsChange)
    expect(vi.mocked(useGetCategoryBreakdown).mock.calls[0][0]).toEqual({
      months: 3,
      top_n: 50,
    })
    expect(vi.mocked(useGetMerchantBreakdown).mock.calls[0][0]).toEqual({
      months: 3,
      top_n: 10,
    })
    await userEvent.click(screen.getByRole("button", { name: "6 months" }))
    expect(onMonthsChange).toHaveBeenCalledWith(6)
  })

  it("shows the empty state with no spending", () => {
    categories({ data: EMPTY })
    merchants({ data: { top_by_spend: [] } })
    const { container } = renderTab()
    expect(screen.getAllByText("No spending in this period.")).toHaveLength(2)
    expect(screen.queryByText("Total spent")).not.toBeInTheDocument()
    expect(container.textContent).not.toContain("€")
  })

  it("keeps data when a refetch fails", () => {
    categories({ data: DATA, isError: true })
    renderTab()
    expect(row("Rent")).toBeInTheDocument()
    expect(screen.queryByText(/Couldn't load/)).not.toBeInTheDocument()
  })

  it("merchants fail on their own", () => {
    merchants({ data: undefined, isError: true })
    renderTab()
    expect(
      screen.getByText("Couldn't load your top merchants."),
    ).toBeInTheDocument()
    expect(row("Rent")).toBeInTheDocument()
  })
})
